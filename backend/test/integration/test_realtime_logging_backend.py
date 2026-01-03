import pytest
import logging
import time
from flask_socketio import SocketIOTestClient
from src.crawl.view.crawler_view import init_realtime_logging
from src.shared.event_bus import EventBus
from run import app, socketio

# 重新加载 logging 配置以确保环境纯净
from src.shared.logging_config import setup_logging

class TestRealtimeLogging:
    
    @pytest.fixture
    def client(self):
        """创建 WebSocket 测试客户端"""
        # 1. 初始化日志配置 (模拟 run.py)
        # 注意：这里会给 error/perf 加 handler，但不会给 crawl_process 加
        setup_logging(socketio=socketio)
        
        # 2. 初始化实时日志 (这步是关键，它应该给 domain.crawl_process 加 handler)
        event_bus = EventBus()
        init_realtime_logging(socketio, event_bus)
        
        # 3. 创建测试客户端
        flask_test_client = app.test_client()
        socketio_test_client = socketio.test_client(
            app, 
            flask_test_client=flask_test_client,
            namespace='/crawl'
        )
        
        yield socketio_test_client
        
        # 清理：断开连接
        if socketio_test_client.is_connected():
            socketio_test_client.disconnect()

    def test_crawl_process_log_broadcast(self, client):
        """验证 domain.crawl_process 的日志是否被广播到 WebSocket"""
        
        # 1. 获取 logger
        logger = logging.getLogger('domain.crawl_process')
        
        # 2. 确保它有 WebSocketLoggingHandler
        handlers = logger.handlers
        ws_handlers = [h for h in handlers if h.__class__.__name__ == 'WebSocketLoggingHandler']
        assert len(ws_handlers) > 0, "domain.crawl_process 应该被添加 WebSocketLoggingHandler"
        
        # 3. 记录当前收到的消息数量
        received = client.get_received('/crawl')
        
        # Sanity Check: 手动发送一条消息，确保测试客户端能收到
        socketio.emit('sanity_check', {'msg': 'hello'}, namespace='/crawl')  
        sanity_received = client.get_received('/crawl')
        assert len(sanity_received) > 0, "测试环境异常：客户端无法收到手动发送的 SocketIO 消息"
        assert sanity_received[0]['name'] == 'sanity_check'
        
        # 4. 瑙﹀彂涓€鏉℃棩蹇
        test_msg = "Test Crawl Process Log Message"
        logger.info(test_msg, extra={'task_id': 'test-123'})
        
        # 5. 检查是否收到消息
        # WebSocket emit 是同步还是异步取决于配置，通常在 test_client 中需要一点时间或直接可获取
        time.sleep(0.1)
        received = client.get_received('/crawl')
        
        # 过滤出 crawl_log 浜嬩欢 (domain.crawl_process 搴旇鍙戦€佸埌 crawl_log)   
        crawl_logs = [
            evt for evt in received
            if evt['name'] == 'crawl_log'
        ]

        # 如果收到的是 tech_log 也要打印出来看看
        tech_logs = [evt for evt in received if evt['name'] == 'tech_log']
        
        assert len(crawl_logs) > 0, f"客户端应该收到 crawl_log 事件。收到: crawl_log={len(crawl_logs)}, tech_log={len(tech_logs)}"
        
        # 6. 验证消息内容
        last_log = crawl_logs[-1]['args'][0]
        assert last_log['message'] == test_msg
        assert last_log['logger'] == 'domain.crawl_process'
        
    def test_handler_deduplication(self, client):
        """验证 init_realtime_logging 是否避免了重复添加 handler"""
        logger = logging.getLogger('infrastructure.error')
        
        ws_handlers = [h for h in logger.handlers if h.__class__.__name__ == 'WebSocketLoggingHandler']
        
        # setup_logging 加了一次，init_realtime_logging 应该发现已存在而不加
        # 但在测试环境中，每次 setup_logging 可能会重置？
        # dictConfig 通常会清空旧的非 root handler，除非 disable_existing_loggers=False
        # 我们的配置是 disable_existing_loggers=False，且是追加模式
        
        # 这里的断言取决于 setup_logging 的具体行为，只要不超过 2 个（理论上应该只有 1 个）
        # 如果代码写得对，应该是 1 个
        assert len(ws_handlers) == 1, f"infrastructure.error 应该只有一个 WebSocketLoggingHandler, 实际有 {len(ws_handlers)}"
