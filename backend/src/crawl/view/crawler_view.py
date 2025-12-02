"""
模块职责
- 提供与前端交互的 RESTful API（健康检查/开始爬取/停止爬取/查询状态）。
- 作为组合根（Composition Root）组装应用层依赖：HTTP客户端、HTML解析器、robots.txt解析器、URL队列、领域服务、应用服务。
- 使用 Flask Blueprint 将接口统一挂载在 `/api/crawl` 前缀下。

设计说明
- 领域驱动设计（DDD）：此模块属于接口层（Interfaces），仅进行输入输出与服务编排，不承载业务规则。
- 任务生命周期由应用服务 `CrawlerService` 管理；实际规则在领域服务与实体（聚合根）中实现。
- 组合根在模块级创建单例以便简化演示；生产实践可改为依赖注入容器或应用工厂内组装。
"""

from flask import Blueprint, jsonify, request
import uuid
from ..services.crawler_service import CrawlerService  # 应用层：负责任务编排、异步调度、状态查询
from ..infrastructure.http_client_impl import HttpClientImpl  # 基础设施：requests 封装的 HTTP 客户端
from ..infrastructure.html_parser_impl import HtmlParserImpl  # 基础设施：BeautifulSoup 封装的 HTML 解析器
from ..infrastructure.robots_txt_parser_impl import RobotsTxtParserImpl  # 基础设施：robots.txt 解析与遵守
from ..infrastructure.url_queue_impl import UrlQueueImpl  # 基础设施：URL 队列，支持 BFS/DFS/优先级
from ..infrastructure.crawl_domain_service_impl import CrawlDomainServiceImpl  # 领域服务具体实现
from ..domain.entity.crawl_task import CrawlTask  # 领域实体：爬取任务聚合根
from ..domain.value_objects.crawl_config import CrawlConfig  # 值对象：任务配置（策略/深度/速率等）
from ..domain.value_objects.crawl_strategy import CrawlStrategy  # 值对象：枚举，BFS/DFS
from src.shared.handlers.websocket_handler import WebSocketLoggingHandler
from src.shared.event_handlers.websocket_handler import WebSocketEventHandler
import logging
from datetime import datetime

bp = Blueprint("crawl", __name__, url_prefix="/api/crawl")

@bp.route("/health", methods=["GET"])
def health():
    # 健康检查：用于前端快速判断后端是否正常运行
    return jsonify({"status": "ok"})

# 组合根（模块级单例）：组装所有依赖
# 说明：简单示例使用单例以便演示；如需更灵活的生命周期与测试隔离，可在应用工厂中组装并通过依赖注入传递
_http = HttpClientImpl()
_parser = HtmlParserImpl()
_robots = RobotsTxtParserImpl()
_queue = UrlQueueImpl()
_domain_service = CrawlDomainServiceImpl(_http, _parser, _robots)
# _service = CrawlerService(_domain_service, _http, _queue)
# 重构：UrlQueue 不再单例注入，而是由 Task 内部管理
_service = CrawlerService(_domain_service, _http)

def inject_event_bus(event_bus):
    """依赖注入：注入事件总线"""
    # 这是一个临时的注入方法，用于在应用启动后将 EventBus 传递给 Service
    # 更好的做法是使用依赖注入框架
    _service._event_bus = event_bus

def init_realtime_logging(socketio, event_bus):
    """
    初始化实时日志能力（供应用启动时调用）
    
    调用此函数将：
    1. 配置 WebSocketLoggingHandler，使技术日志（错误/性能）能推送到前端
    2. 配置 WebSocketEventHandler，使业务日志（爬取进度）能推送到前端
    """
    # 1. 确保 Service 拥有 EventBus
    if not hasattr(_service, '_event_bus') or _service._event_bus is None:
        _service._event_bus = event_bus

    # 2. 配置业务日志推送 (Domain Events -> WebSocket)
    # 订阅 WebSocketEventHandler 到事件总线
    ws_event_handler = WebSocketEventHandler(socketio)
    event_bus.subscribe_to_all(ws_event_handler.handle)
    
    # 3. 配置技术日志推送 (Logger -> WebSocket)
    # 获取技术日志 Logger
    tech_loggers = [
        logging.getLogger('infrastructure.error'),
        logging.getLogger('infrastructure.perf')
    ]
    
    # 创建 handler
    ws_log_handler = WebSocketLoggingHandler(socketio)
    # 设置简单格式，具体字段由 handler 内部处理
    ws_log_handler.setFormatter(logging.Formatter('%(message)s'))
    
    for logger in tech_loggers:
        # 避免重复添加 (如果 run.py 或 logging_config 已经添加过)
        if not any(isinstance(h, WebSocketLoggingHandler) for h in logger.handlers):
            logger.addHandler(ws_log_handler)

@bp.route("/logs/test_broadcast", methods=["POST"])
def test_broadcast_log():
    """
    [测试接口] 触发测试日志以验证实时推送功能
    前端调用此接口后，应能在 WebSocket 的 'tech_log' 和 'crawl_log' 频道收到消息
    """
    try:
        # 1. 触发一条技术错误日志 (推送到 tech_log)
        error_logger = logging.getLogger('infrastructure.error')
        error_logger.error("Test Error: Real-time log connection test", extra={'component': 'api_test'})
        
        # 2. 触发一条业务日志 (推送到 crawl_log)
        # 尝试通过 EventBus 发布模拟事件
        if hasattr(_service, '_event_bus') and _service._event_bus:
            class MockEvent:
                def __init__(self):
                    self.event_type = "TEST_LOG"
                    self.task_id = "system_test"
                    self.data = {"message": "Test crawl log via EventBus"}
                    self.timestamp = datetime.now()
            
            _service._event_bus.publish(MockEvent())
        else:
            # 备用：如果 EventBus 未连接，记录到 domain logger
            domain_logger = logging.getLogger('domain.crawl_process')
            domain_logger.info("Test Process: Crawl process active (EventBus not connected)", extra={'task_id': 'system_test'})
        
        return jsonify({
            "status": "ok", 
            "message": "Test logs broadcasted to WebSocket channels"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/create", methods=["POST"])
def create():
    """创建爬取任务（不自动启动）"""
    data = request.get_json(force=True) or {}
    start_url = data.get("start_url")
    strategy = data.get("strategy", "BFS")
    max_depth = int(data.get("max_depth", 3))
    max_pages = int(data.get("max_pages", 100))
    interval = float(data.get("interval", 1.0))
    allow_domains = data.get("allow_domains", [])

    if not start_url:
        return jsonify({"error": "start_url is required"}), 400

    try:
        config = CrawlConfig(
            start_url=start_url,
            strategy=CrawlStrategy(strategy),
            max_depth=max_depth,
            max_pages=max_pages,
            request_interval=interval,
            allow_domains=allow_domains,
        )
        
        task_id = _service.create_crawl_task(config)
        return jsonify({"task_id": task_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route("/start/<task_id>", methods=["POST"])
def start(task_id: str):
    """启动已创建的爬取任务"""
    try:
        _service.start_crawl_task(task_id)
        return jsonify({"status": "started", "task_id": task_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route("/config/<task_id>", methods=["POST"])
def update_config(task_id: str):
    """更新任务配置（interval/max_pages/max_depth）"""
    data = request.get_json(force=True) or {}
    interval = data.get("interval")
    max_pages = data.get("max_pages")
    max_depth = data.get("max_depth")
    
    if interval: interval = float(interval)
    if max_pages: max_pages = int(max_pages)
    if max_depth: max_depth = int(max_depth)
    
    try:
        _service.set_crawl_config(task_id, interval=interval, max_pages=max_pages, max_depth=max_depth)
        return jsonify({"status": "updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route("/pause/<task_id>", methods=["POST"])
def pause(task_id: str):
    """暂停爬取任务"""
    try:
        _service.pause_crawl_task(task_id)
        return jsonify({"status": "paused", "task_id": task_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route("/resume/<task_id>", methods=["POST"])
def resume(task_id: str):
    """恢复爬取任务"""
    try:
        _service.resume_crawl_task(task_id)
        return jsonify({"status": "resumed", "task_id": task_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route("/stop/<task_id>", methods=["POST"])
def stop(task_id: str):
    # 停止指定任务（软停止）：
    # - 标记停止并清空队列，循环检测到停止信号后结束
    try:
        _service.stop_crawl_task(task_id)
        return jsonify({"status": "stopping", "task_id": task_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route("/queue/add", methods=["POST"])
def add_url_to_queue():
    """逐个添加URL到队列"""
    data = request.get_json(force=True) or {}
    task_id = data.get("task_id")
    url = data.get("url")
    priority = int(data.get("priority", 0))
    depth = int(data.get("depth", 0))
    
    if not task_id or not url:
        return jsonify({"error": "task_id and url are required"}), 400
        
    try:
        _service.add_url(task_id, url, depth, priority)
        return jsonify({"status": "added", "url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/status/<task_id>", methods=["GET"])
def status(task_id: str):
    # 查询任务运行状态，返回字段：
    # - task_id: 任务ID
    # - status: 任务状态（PENDING/RUNNING/PAUSED/COMPLETED/FAILED/STOPPED）
    # - visited_count: 已访问 URL 数量
    # - result_count: 提取到的页面结果数量
    # - queue_size: 当前队列长度
    # - current_depth: 当前处理的队列深度
    return jsonify(_service.get_task_status(task_id))

@bp.route("/results/<task_id>", methods=["GET"])
def results(task_id: str):
    """查询任务的最新结果列表"""
    try:
        results = _service.get_task_results(task_id)
        # 将结果对象转换为字典列表
        return jsonify([
            {
                "url": r.url,
                "title": r.title,
                "crawled_at": r.crawled_at.isoformat() if r.crawled_at else None,
                "pdf_count": len(r.pdf_links)
            } 
            for r in results
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 400
