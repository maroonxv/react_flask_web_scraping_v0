"""
UrlQueueImpl 的 pytest 测试套件
覆盖：三种策略（BFS/DFS/PRIORITY）、深度限制、队列操作、边界情况
"""

import pytest
from collections import deque
import sys
import os

# 添加 backend 目录到系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.crawl.infrastructure.url_queue_impl import UrlQueueImpl
from src.crawl.domain.value_objects.queued_url import QueuedUrl


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def queue():
    """创建 UrlQueueImpl 实例"""
    return UrlQueueImpl()


@pytest.fixture
def bfs_queue(queue):
    """创建已初始化的 BFS 队列"""
    queue.initialize("http://example.com", strategy="BFS", max_depth=3)
    return queue


@pytest.fixture
def dfs_queue(queue):
    """创建已初始化的 DFS 队列"""
    queue.initialize("http://example.com", strategy="DFS", max_depth=3)
    return queue


@pytest.fixture
def priority_queue(queue):
    """创建已初始化的 PRIORITY 队列"""
    queue.initialize("http://example.com", strategy="PRIORITY", max_depth=3)
    return queue


# ============================================================================
# 初始化测试
# ============================================================================

class TestInitialization:
    """测试初始化功能"""

    def test_default_initialization(self, queue):
        """测试默认状态"""
        assert queue._strategy == "BFS"
        assert queue._max_depth == 3
        assert queue._current_depth == 0
        assert queue.is_empty()

    def test_initialize_bfs_strategy(self, queue):
        """测试 BFS 策略初始化"""
        queue.initialize("http://example.com", strategy="BFS", max_depth=5)
        
        assert queue._strategy == "BFS"
        assert queue._max_depth == 5
        assert queue.size() == 1  # 起始 URL
        
        # 验证起始 URL 被添加
        url = queue.dequeue()
        assert url.url == "http://example.com"
        assert url.depth == 0

    def test_initialize_dfs_strategy(self, queue):
        """测试 DFS 策略初始化"""
        queue.initialize("http://example.com", strategy="DFS", max_depth=2)
        
        assert queue._strategy == "DFS"
        assert queue._max_depth == 2
        assert queue.size() == 1

    def test_initialize_priority_strategy(self, queue):
        """测试 PRIORITY 策略初始化"""
        queue.initialize("http://example.com", strategy="PRIORITY", max_depth=4)
        
        assert queue._strategy == "PRIORITY"
        assert queue._max_depth == 4
        assert queue.size() == 1

    def test_initialize_invalid_strategy(self, queue):
        """测试无效策略抛出异常"""
        with pytest.raises(ValueError) as exc_info:
            queue.initialize("http://example.com", strategy="INVALID")
        
        assert "不支持的策略" in str(exc_info.value)
        assert "INVALID" in str(exc_info.value)

    def test_initialize_clears_existing_queue(self, queue):
        """测试重新初始化会清空现有队列"""
        # 先初始化 BFS 并添加一些 URL
        queue.initialize("http://example.com", strategy="BFS")
        queue.enqueue("http://example.com/page1", depth=1)
        queue.enqueue("http://example.com/page2", depth=1)
        assert queue.size() == 3
        
        # 重新初始化为 DFS
        queue.initialize("http://newsite.com", strategy="DFS", max_depth=2)
        
        assert queue._strategy == "DFS"
        assert queue.size() == 1
        url = queue.dequeue()
        assert url.url == "http://newsite.com"

    def test_initialize_start_url_has_priority(self, queue):
        """测试起始 URL 的默认优先级"""
        queue.initialize("http://example.com", strategy="PRIORITY")
        
        url = queue.dequeue()
        assert url.priority == 100  # 默认优先级


# ============================================================================
# BFS 策略测试
# ============================================================================

class TestBFSStrategy:
    """测试 BFS（广度优先）策略"""

    def test_bfs_fifo_order(self, bfs_queue):
        """测试 BFS FIFO（先进先出）顺序"""
        # 移除起始 URL
        bfs_queue.dequeue()
        
        # 添加多个 URL
        bfs_queue.enqueue("http://example.com/page1", depth=1)
        bfs_queue.enqueue("http://example.com/page2", depth=1)
        bfs_queue.enqueue("http://example.com/page3", depth=1)
        
        # 验证 FIFO 顺序
        assert bfs_queue.dequeue().url == "http://example.com/page1"
        assert bfs_queue.dequeue().url == "http://example.com/page2"
        assert bfs_queue.dequeue().url == "http://example.com/page3"

    def test_bfs_depth_tracking(self, bfs_queue):
        """测试 BFS 深度跟踪"""
        bfs_queue.dequeue()  # 移除起始 URL (depth=0)
        
        bfs_queue.enqueue("http://example.com/d1", depth=1)
        bfs_queue.enqueue("http://example.com/d2", depth=2)
        
        url1 = bfs_queue.dequeue()
        assert url1.depth == 1
        assert bfs_queue.get_current_depth() == 1
        
        url2 = bfs_queue.dequeue()
        assert url2.depth == 2
        assert bfs_queue.get_current_depth() == 2

    def test_bfs_respects_max_depth(self, bfs_queue):
        """测试 BFS 遵守最大深度限制"""
        bfs_queue.clear()
        bfs_queue.initialize("http://example.com", strategy="BFS", max_depth=2)
        bfs_queue.dequeue()  # 移除起始 URL
        
        # 添加不同深度的 URL
        bfs_queue.enqueue("http://example.com/d1", depth=1)  # 允许
        bfs_queue.enqueue("http://example.com/d2", depth=2)  # 允许
        bfs_queue.enqueue("http://example.com/d3", depth=3)  # 超过限制，不添加
        
        assert bfs_queue.size() == 2
        assert bfs_queue.dequeue().url == "http://example.com/d1"
        assert bfs_queue.dequeue().url == "http://example.com/d2"
        assert bfs_queue.is_empty()

    def test_bfs_mixed_depths(self, bfs_queue):
        """测试 BFS 混合深度的 URL"""
        bfs_queue.dequeue()  # 移除起始 URL
        
        # 按不同顺序添加不同深度的 URL
        bfs_queue.enqueue("http://example.com/a", depth=1)
        bfs_queue.enqueue("http://example.com/b", depth=2)
        bfs_queue.enqueue("http://example.com/c", depth=1)
        bfs_queue.enqueue("http://example.com/d", depth=3)
        
        # BFS 应该按插入顺序输出（不按深度排序）
        assert bfs_queue.dequeue().url == "http://example.com/a"
        assert bfs_queue.dequeue().url == "http://example.com/b"
        assert bfs_queue.dequeue().url == "http://example.com/c"
        assert bfs_queue.dequeue().url == "http://example.com/d"


# ============================================================================
# DFS 策略测试
# ============================================================================

class TestDFSStrategy:
    """测试 DFS（深度优先）策略"""

    def test_dfs_lifo_order(self, dfs_queue):
        """测试 DFS LIFO（后进先出）顺序"""
        dfs_queue.dequeue()  # 移除起始 URL
        
        # 添加多个 URL
        dfs_queue.enqueue("http://example.com/page1", depth=1)
        dfs_queue.enqueue("http://example.com/page2", depth=1)
        dfs_queue.enqueue("http://example.com/page3", depth=1)
        
        # 验证 LIFO 顺序（后进先出）
        assert dfs_queue.dequeue().url == "http://example.com/page3"
        assert dfs_queue.dequeue().url == "http://example.com/page2"
        assert dfs_queue.dequeue().url == "http://example.com/page1"

    def test_dfs_depth_tracking(self, dfs_queue):
        """测试 DFS 深度跟踪"""
        dfs_queue.dequeue()  # 移除起始 URL
        
        dfs_queue.enqueue("http://example.com/d1", depth=1)
        dfs_queue.enqueue("http://example.com/d3", depth=3)
        
        url1 = dfs_queue.dequeue()
        assert url1.depth == 3  # LIFO，最后添加的先出
        assert dfs_queue.get_current_depth() == 3

    def test_dfs_respects_max_depth(self, dfs_queue):
        """测试 DFS 遵守最大深度限制"""
        dfs_queue.clear()
        dfs_queue.initialize("http://example.com", strategy="DFS", max_depth=2)
        dfs_queue.dequeue()
        
        dfs_queue.enqueue("http://example.com/d1", depth=1)
        dfs_queue.enqueue("http://example.com/d2", depth=2)
        dfs_queue.enqueue("http://example.com/d3", depth=3)  # 超过限制
        dfs_queue.enqueue("http://example.com/d4", depth=4)  # 超过限制
        
        assert dfs_queue.size() == 2

    def test_dfs_deep_first_behavior(self, dfs_queue):
        """测试 DFS 深度优先行为"""
        dfs_queue.dequeue()  # 移除起始 URL
        
        # 模拟深度优先：先添加浅层，再添加深层
        dfs_queue.enqueue("http://example.com/shallow", depth=1)
        dfs_queue.enqueue("http://example.com/deep1", depth=2)
        dfs_queue.enqueue("http://example.com/deep2", depth=3)
        
        # DFS 应该先处理后添加的（深层的）
        assert dfs_queue.dequeue().url == "http://example.com/deep2"
        assert dfs_queue.dequeue().url == "http://example.com/deep1"
        assert dfs_queue.dequeue().url == "http://example.com/shallow"


# ============================================================================
# PRIORITY 策略测试
# ============================================================================

class TestPriorityStrategy:
    """测试 PRIORITY（优先级）策略"""

    def test_priority_high_first(self, priority_queue):
        """测试高优先级先出"""
        priority_queue.dequeue()  # 移除起始 URL
        
        # 添加不同优先级的 URL
        priority_queue.enqueue("http://example.com/low", depth=1, priority=10)
        priority_queue.enqueue("http://example.com/high", depth=1, priority=100)
        priority_queue.enqueue("http://example.com/medium", depth=1, priority=50)
        
        # 应该按优先级从高到低输出
        assert priority_queue.dequeue().url == "http://example.com/high"
        assert priority_queue.dequeue().url == "http://example.com/medium"
        assert priority_queue.dequeue().url == "http://example.com/low"

    def test_priority_same_priority_fifo(self, priority_queue):
        """测试相同优先级按插入顺序（FIFO）"""
        priority_queue.dequeue()
        
        # 添加相同优先级的 URL
        priority_queue.enqueue("http://example.com/first", depth=1, priority=50)
        priority_queue.enqueue("http://example.com/second", depth=1, priority=50)
        priority_queue.enqueue("http://example.com/third", depth=1, priority=50)
        
        # 相同优先级应该按插入顺序
        assert priority_queue.dequeue().url == "http://example.com/first"
        assert priority_queue.dequeue().url == "http://example.com/second"
        assert priority_queue.dequeue().url == "http://example.com/third"

    def test_priority_negative_values(self, priority_queue):
        """测试负优先级"""
        priority_queue.dequeue()
        
        priority_queue.enqueue("http://example.com/positive", depth=1, priority=10)
        priority_queue.enqueue("http://example.com/negative", depth=1, priority=-5)
        priority_queue.enqueue("http://example.com/zero", depth=1, priority=0)
        
        # 正数 > 0 > 负数
        assert priority_queue.dequeue().url == "http://example.com/positive"
        assert priority_queue.dequeue().url == "http://example.com/zero"
        assert priority_queue.dequeue().url == "http://example.com/negative"

    def test_priority_respects_max_depth(self, priority_queue):
        """测试 PRIORITY 遵守最大深度"""
        priority_queue.clear()
        priority_queue.initialize("http://example.com", strategy="PRIORITY", max_depth=2)
        priority_queue.dequeue()
        
        priority_queue.enqueue("http://example.com/d1", depth=1, priority=50)
        priority_queue.enqueue("http://example.com/d2", depth=2, priority=100)
        priority_queue.enqueue("http://example.com/d3", depth=3, priority=200)  # 超过限制
        
        assert priority_queue.size() == 2
        # 即使 d3 优先级最高，也不应被添加
        assert priority_queue.dequeue().url == "http://example.com/d2"

    def test_priority_large_values(self, priority_queue):
        """测试极大优先级值"""
        priority_queue.dequeue()
        
        priority_queue.enqueue("http://example.com/huge", depth=1, priority=999999)
        priority_queue.enqueue("http://example.com/small", depth=1, priority=1)
        
        assert priority_queue.dequeue().url == "http://example.com/huge"
        assert priority_queue.dequeue().url == "http://example.com/small"

    def test_priority_depth_tracking(self, priority_queue):
        """测试 PRIORITY 策略的深度跟踪"""
        priority_queue.dequeue()
        
        priority_queue.enqueue("http://example.com/d1", depth=1, priority=50)
        priority_queue.enqueue("http://example.com/d3", depth=3, priority=100)
        
        url = priority_queue.dequeue()
        assert url.depth == 3  # 优先级高的先出
        assert priority_queue.get_current_depth() == 3


# ============================================================================
# 队列操作测试
# ============================================================================

class TestQueueOperations:
    """测试基本队列操作"""

    def test_is_empty_on_new_queue(self, queue):
        """测试新队列为空"""
        assert queue.is_empty()

    def test_is_empty_after_initialize(self, bfs_queue):
        """测试初始化后不为空（有起始 URL）"""
        assert not bfs_queue.is_empty()

    def test_is_empty_after_dequeue_all(self, bfs_queue):
        """测试取出所有元素后为空"""
        while not bfs_queue.is_empty():
            bfs_queue.dequeue()
        
        assert bfs_queue.is_empty()

    def test_size_empty_queue(self, queue):
        """测试空队列大小为 0"""
        assert queue.size() == 0

    def test_size_after_enqueue(self, bfs_queue):
        """测试添加后大小增加"""
        initial_size = bfs_queue.size()
        
        bfs_queue.enqueue("http://example.com/page1", depth=1)
        bfs_queue.enqueue("http://example.com/page2", depth=1)
        
        assert bfs_queue.size() == initial_size + 2

    def test_size_after_dequeue(self, bfs_queue):
        """测试取出后大小减少"""
        bfs_queue.enqueue("http://example.com/page1", depth=1)
        size_before = bfs_queue.size()
        
        bfs_queue.dequeue()
        
        assert bfs_queue.size() == size_before - 1

    def test_clear_empty_queue(self, queue):
        """测试清空空队列不报错"""
        queue.clear()
        assert queue.is_empty()

    def test_clear_populated_queue(self, bfs_queue):
        """测试清空有数据的队列"""
        bfs_queue.enqueue("http://example.com/page1", depth=1)
        bfs_queue.enqueue("http://example.com/page2", depth=1)
        assert bfs_queue.size() > 0
        
        bfs_queue.clear()
        
        assert bfs_queue.is_empty()
        assert bfs_queue.size() == 0

    def test_get_current_depth_initial(self, bfs_queue):
        """测试初始深度"""
        # 未取出任何 URL 时
        assert bfs_queue.get_current_depth() == 0

    def test_get_current_depth_after_dequeue(self, bfs_queue):
        """测试取出 URL 后更新深度"""
        bfs_queue.enqueue("http://example.com/d2", depth=2)
        
        bfs_queue.dequeue()  # 起始 URL, depth=0
        assert bfs_queue.get_current_depth() == 0
        
        bfs_queue.dequeue()  # depth=2 的 URL
        assert bfs_queue.get_current_depth() == 2


# ============================================================================
# dequeue 边界情况测试
# ============================================================================

class TestDequeueEdgeCases:
    """测试 dequeue 边界情况"""

    def test_dequeue_empty_bfs_queue(self, queue):
        """测试从空 BFS 队列 dequeue"""
        queue.initialize("http://example.com", strategy="BFS")
        queue.clear()
        
        result = queue.dequeue()
        assert result is None

    def test_dequeue_empty_dfs_queue(self, queue):
        """测试从空 DFS 队列 dequeue"""
        queue.initialize("http://example.com", strategy="DFS")
        queue.clear()
        
        result = queue.dequeue()
        assert result is None

    def test_dequeue_empty_priority_queue(self, queue):
        """测试从空 PRIORITY 队列 dequeue"""
        queue.initialize("http://example.com", strategy="PRIORITY")
        queue.clear()
        
        result = queue.dequeue()
        assert result is None

    def test_multiple_dequeue_on_empty(self, bfs_queue):
        """测试多次从空队列 dequeue"""
        bfs_queue.clear()
        
        assert bfs_queue.dequeue() is None
        assert bfs_queue.dequeue() is None
        assert bfs_queue.dequeue() is None

    def test_dequeue_single_element(self, bfs_queue):
        """测试只有一个元素时 dequeue"""
        bfs_queue.clear()
        bfs_queue.enqueue("http://example.com/single", depth=1)
        
        url = bfs_queue.dequeue()
        assert url.url == "http://example.com/single"
        assert bfs_queue.is_empty()


# ============================================================================
# enqueue 边界情况测试
# ============================================================================

class TestEnqueueEdgeCases:
    """测试 enqueue 边界情况"""

    def test_enqueue_at_max_depth(self, bfs_queue):
        """测试在最大深度添加 URL"""
        bfs_queue.clear()
        bfs_queue.initialize("http://example.com", strategy="BFS", max_depth=3)
        bfs_queue.dequeue()
        
        # 深度 = max_depth 应该被允许
        bfs_queue.enqueue("http://example.com/max", depth=3)
        assert bfs_queue.size() == 1

    def test_enqueue_exceed_max_depth(self, bfs_queue):
        """测试超过最大深度不添加"""
        bfs_queue.clear()
        bfs_queue.initialize("http://example.com", strategy="BFS", max_depth=3)
        bfs_queue.dequeue()
        
        # 深度 > max_depth 不应被添加
        bfs_queue.enqueue("http://example.com/over", depth=4)
        assert bfs_queue.size() == 0

    def test_enqueue_depth_zero(self, bfs_queue):
        """测试添加深度为 0 的 URL"""
        bfs_queue.dequeue()  # 移除起始 URL
        
        bfs_queue.enqueue("http://example.com/zero", depth=0)
        
        url = bfs_queue.dequeue()
        assert url.depth == 0

    def test_enqueue_negative_depth(self, bfs_queue):
        """测试添加负深度（异常情况）"""
        bfs_queue.dequeue()
        
        # 负深度应该被允许（没有验证）
        bfs_queue.enqueue("http://example.com/negative", depth=-1)
        
        # 实现中没有检查负数，所以会被添加
        assert bfs_queue.size() == 1

    def test_enqueue_duplicate_urls(self, bfs_queue):
        """测试添加重复 URL（不去重）"""
        bfs_queue.dequeue()
        
        bfs_queue.enqueue("http://example.com/dup", depth=1)
        bfs_queue.enqueue("http://example.com/dup", depth=1)
        bfs_queue.enqueue("http://example.com/dup", depth=1)
        
        # 实现中不去重，应该添加 3 次
        assert bfs_queue.size() == 3


# ============================================================================
# 策略切换和混合测试
# ============================================================================

class TestStrategySwitching:
    """测试策略切换"""

    def test_switch_from_bfs_to_dfs(self, queue):
        """测试从 BFS 切换到 DFS"""
        queue.initialize("http://example.com", strategy="BFS")
        queue.enqueue("http://example.com/bfs1", depth=1)
        queue.enqueue("http://example.com/bfs2", depth=1)
        
        # 切换到 DFS
        queue.initialize("http://newsite.com", strategy="DFS")
        
        assert queue._strategy == "DFS"
        assert queue.size() == 1  # 只有新的起始 URL
        assert queue.dequeue().url == "http://newsite.com"

    def test_switch_from_priority_to_bfs(self, queue):
        """测试从 PRIORITY 切换到 BFS"""
        queue.initialize("http://example.com", strategy="PRIORITY")
        queue.enqueue("http://example.com/p1", depth=1, priority=100)
        
        queue.initialize("http://newsite.com", strategy="BFS")
        
        assert queue._strategy == "BFS"
        assert queue.size() == 1

    def test_reinitialize_same_strategy(self, bfs_queue):
        """测试重新初始化相同策略"""
        bfs_queue.enqueue("http://example.com/old", depth=1)
        old_size = bfs_queue.size()
        
        bfs_queue.initialize("http://fresh.com", strategy="BFS", max_depth=5)
        
        assert bfs_queue._max_depth == 5
        assert bfs_queue.size() == 1  # 清空后只有新起始 URL


# ============================================================================
# 压力和性能测试
# ============================================================================

class TestStressAndPerformance:
    """测试大量数据处理"""

    def test_large_number_of_urls_bfs(self, bfs_queue):
        """测试 BFS 处理大量 URL"""
        bfs_queue.clear()
        
        # 添加 1000 个 URL
        for i in range(1000):
            bfs_queue.enqueue(f"http://example.com/page{i}", depth=1)
        
        assert bfs_queue.size() == 1000
        
        # 验证 FIFO 顺序
        for i in range(5):
            url = bfs_queue.dequeue()
            assert url.url == f"http://example.com/page{i}"

    def test_large_number_of_urls_priority(self, priority_queue):
        """测试 PRIORITY 处理大量 URL"""
        priority_queue.clear()
        
        # 添加 100 个随机优先级的 URL
        import random
        priorities = []
        for i in range(100):
            priority = random.randint(1, 100)
            priorities.append(priority)
            priority_queue.enqueue(f"http://example.com/page{i}", depth=1, priority=priority)
        
        # 验证按优先级排序
        prev_priority = float('inf')
        for _ in range(100):
            url = priority_queue.dequeue()
            assert url.priority <= prev_priority
            prev_priority = url.priority

    def test_alternating_enqueue_dequeue(self, bfs_queue):
        """测试交替添加和取出"""
        bfs_queue.dequeue()  # 移除起始 URL
        
        for i in range(10):
            bfs_queue.enqueue(f"http://example.com/add{i}", depth=1)
            if i % 2 == 0:
                bfs_queue.dequeue()
        
        # 应该剩余一些 URL
        assert bfs_queue.size() > 0


# ============================================================================
# 完整流程测试
# ============================================================================

class TestCompleteWorkflow:
    """测试完整的爬取流程模拟"""

    def test_bfs_crawl_simulation(self, queue):
        """模拟 BFS 爬取流程"""
        # 初始化
        queue.initialize("http://example.com", strategy="BFS", max_depth=2)
        
        # 处理起始 URL
        current = queue.dequeue()
        assert current.depth == 0
        
        # 从起始页发现 2 个链接（深度 1）
        queue.enqueue("http://example.com/page1", depth=1)
        queue.enqueue("http://example.com/page2", depth=1)
        
        # 处理深度 1 的页面
        page1 = queue.dequeue()
        assert page1.depth == 1
        
        # 从 page1 发现 1 个链接（深度 2）
        queue.enqueue("http://example.com/page1/sub", depth=2)
        
        # 继续处理
        page2 = queue.dequeue()
        assert page2.depth == 1
        
        # 从 page2 发现深度 3 的链接（应该被拒绝）
        queue.enqueue("http://example.com/page2/deep", depth=3)
        
        # 最后只剩深度 2 的页面
        final = queue.dequeue()
        assert final.depth == 2
        assert queue.is_empty()

    def test_priority_crawl_simulation(self, queue):
        """模拟优先级爬取流程"""
        queue.initialize("http://example.com", strategy="PRIORITY", max_depth=3)
        queue.dequeue()  # 移除起始 URL
        
        # 添加不同优先级的 URL（模拟根据链接位置/文本评分）
        queue.enqueue("http://example.com/important", depth=1, priority=100)  # 重要链接
        queue.enqueue("http://example.com/normal", depth=1, priority=50)     # 普通链接
        queue.enqueue("http://example.com/footer", depth=1, priority=10)     # 页脚链接
        
        # 应该优先处理重要链接
        assert queue.dequeue().url == "http://example.com/important"
        assert queue.dequeue().url == "http://example.com/normal"
        assert queue.dequeue().url == "http://example.com/footer"


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == '__main__':
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--cov=src.crawl.infrastructure.queue.url_queue_impl',
        '--cov-report=html',
        '--cov-report=term-missing'
    ])
