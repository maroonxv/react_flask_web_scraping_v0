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

from flask import Blueprint, jsonify, request, send_file
import uuid
import pandas as pd
from io import BytesIO
from ..services.crawler_service import CrawlerService  # 应用层：负责任务编排、异步调度、状态查询
from ..infrastructure.http_client_impl import HttpClientImpl  # 基础设施：requests 封装的 HTTP 客户端
from ..infrastructure.playwright_client import PlaywrightClient
from ..infrastructure.hybrid_http_client import HybridHttpClient
from ..infrastructure.html_parser_impl import HtmlParserImpl  # 基础设施：BeautifulSoup 封装的 HTML 解析器
from ..infrastructure.robots_txt_parser_impl import RobotsTxtParserImpl  # 基础设施：robots.txt 解析与遵守
from ..infrastructure.url_queue_impl import UrlQueueImpl  # 基础设施：URL 队列，支持 BFS/DFS/优先级
from ..infrastructure.crawl_domain_service_impl import CrawlDomainServiceImpl  # 领域服务具体实现
from ..infrastructure.database.sqlalchemy_crawl_dao_impl import SqlAlchemyCrawlDaoImpl # 基础设施：数据库DAO
from ..infrastructure.database.crawl_repository_impl import CrawlRepositoryImpl # 基础设施：仓储实现
from src.shared.db_manager import init_db # 基础设施：DB初始化

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

# 1. 初始化数据库
init_db()

# 2. 创建基础设施与服务
_static_http = HttpClientImpl()
_pw_client = PlaywrightClient()
_http = HybridHttpClient(_static_http, _pw_client)
_parser = HtmlParserImpl()
_robots = RobotsTxtParserImpl()
_domain_service = CrawlDomainServiceImpl(_http, _parser, _robots)

from ..infrastructure.binary_http_client_impl import BinaryHttpClientImpl
from ..infrastructure.pdf_content_extractor_impl import PdfContentExtractorImpl
from ..infrastructure.pdf_domain_service_impl import PdfDomainServiceImpl

# 3. 创建持久化层
_dao = SqlAlchemyCrawlDaoImpl() # 使用默认 scoped_session
_repository = CrawlRepositoryImpl(_dao)

# PDF 服务组装
_binary_http = BinaryHttpClientImpl()
_pdf_extractor = PdfContentExtractorImpl()
_pdf_service = PdfDomainServiceImpl(_binary_http, _pdf_extractor)

# 4. 创建应用服务
# 重构：UrlQueue 不再单例注入，而是由 Task 内部管理
_service = CrawlerService(_domain_service, _http, _repository, pdf_domain_service=_pdf_service)

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
    # 分开配置：
    # - infrastructure.* -> tech_log (默认)
    # - domain.crawl_process -> crawl_log (业务过程)
    
    # 3.1 技术日志
    tech_handler = WebSocketLoggingHandler(socketio, event_name='tech_log')
    tech_handler.setFormatter(logging.Formatter('%(message)s'))
    
    tech_loggers = [
        logging.getLogger('infrastructure.error'),
        logging.getLogger('infrastructure.perf')
    ]
    for logger in tech_loggers:
        if not any(isinstance(h, WebSocketLoggingHandler) and h._event_name == 'tech_log' for h in logger.handlers):
            logger.addHandler(tech_handler)
            
    # 3.2 业务过程日志 (ScoreManager, Hybrid, etc.)
    process_handler = WebSocketLoggingHandler(socketio, event_name='crawl_log')
    process_handler.setFormatter(logging.Formatter('%(message)s'))
    
    process_loggers = [
        logging.getLogger('domain.crawl_process'),
        logging.getLogger('domain.task_lifecycle')
    ]
    for logger in process_loggers:
        if not any(isinstance(h, WebSocketLoggingHandler) and h._event_name == 'crawl_log' for h in logger.handlers):
            logger.addHandler(process_handler)

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

@bp.route("/tasks", methods=["GET"])
def list_tasks():
    """获取所有爬取任务（历史记录）"""
    try:
        tasks = _service.get_all_tasks()
        task_list = []
        for t in tasks:
            task_list.append({
                "id": t.id,
                "name": t.name,
                "status": t.status.value,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "start_url": t.config.start_url,
                "visited_count": len(t.visited_urls)
            })
        return jsonify(task_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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
    priority_domains = data.get("priority_domains", [])
    blacklist = data.get("blacklist", [])
    name = data.get("name")  # Extract name

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
            priority_domains=priority_domains,
            blacklist=blacklist
        )
        
        task_id = _service.create_crawl_task(config, name=name)
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
    status_data = _service.get_task_status(task_id)
    if "error" in status_data:
        return jsonify(status_data), 404
        
    return jsonify(status_data)

@bp.route("/export/<task_id>", methods=["GET"])
def export_results(task_id):
    """导出任务结果为 Excel 文件"""
    results = _service.get_task_results(task_id)
    if not results:
        return jsonify({"error": "No results found or task does not exist"}), 404
    
    # Convert results to list of dicts
    data = []
    for res in results:
        data.append({
            "标题": res.title,
            "URL": res.url,
            "深度": res.depth,
            "作者": res.author,
            "摘要": res.abstract,
            "关键词": ", ".join(res.keywords) if res.keywords else "",
            "发布时间": res.publish_date,
            "PDF数量": len(res.pdf_links) if res.pdf_links else 0,
            "PDF链接": ", ".join(res.pdf_links) if res.pdf_links else "",
            "爬取时间": res.crawled_at.isoformat() if res.crawled_at else None
        })
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    # Use xlsxwriter engine for better compatibility, or default openpyxl
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='结果')
    
    output.seek(0)
    
    filename = f"crawl_results_{task_id}.xlsx"
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@bp.route("/results/<task_id>", methods=["GET"])
def results(task_id: str):
    """查询任务的最新结果列表"""
    try:
        results = _service.get_task_results(task_id)
        return jsonify([
            {
                "url": r.url,
                "title": r.title,
                "depth": r.depth,
                "author": r.author,
                "abstract": r.abstract,
                "keywords": r.keywords,
                "crawled_at": r.crawled_at.isoformat() if r.crawled_at else None,
                "pdf_count": len(r.pdf_links),
                "tags": r.tags
            } 
            for r in results
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route("/results/pdf/<task_id>", methods=["GET"])
def pdf_results(task_id: str):
    """查询任务的 PDF 爬取结果列表"""
    try:
        results = _service.get_pdf_results(task_id)
        return jsonify([
            {
                "url": r.url,
                "is_success": r.is_success,
                "error_message": r.error_message,
                "title": r.pdf_content.metadata.title if r.is_success and r.pdf_content and r.pdf_content.metadata else None,
                "author": r.pdf_content.metadata.author if r.is_success and r.pdf_content and r.pdf_content.metadata else None,
                "page_count": r.pdf_content.metadata.page_count if r.is_success and r.pdf_content and r.pdf_content.metadata else 0,
                "content_preview": r.pdf_content.text_content[:200] + "..." if r.is_success and r.pdf_content and r.pdf_content.text_content else None,
                "depth": r.depth,
                "crawled_at": r.crawled_at.isoformat() if r.crawled_at else None
            }
            for r in results
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 400
