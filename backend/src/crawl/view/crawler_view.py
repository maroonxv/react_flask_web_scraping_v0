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
_service = CrawlerService(_domain_service, _http, _queue)

@bp.route("/start", methods=["POST"])
def start():
    # 启动爬取任务
    # 请求体（JSON）：
    # - start_url: 起始 URL（必填）
    # - strategy: 爬取策略（"BFS"/"DFS"），默认 "BFS"
    # - max_depth: 最大深度，默认 3
    # - max_pages: 最大页面数量，默认 100
    # - interval: 请求间隔（秒），默认 1.0
    # - allow_domains: 允许的域名白名单（数组），默认空（不限制）
    data = request.get_json(force=True) or {}
    start_url = data.get("start_url")
    strategy = data.get("strategy", "BFS")
    max_depth = int(data.get("max_depth", 3))
    max_pages = int(data.get("max_pages", 100))
    interval = float(data.get("interval", 1.0))
    allow_domains = data.get("allow_domains", [])

    # 基本校验：起始 URL 必填
    if not start_url:
        return jsonify({"error": "start_url is required"}), 400

    try:
        # 构造任务配置并创建任务聚合根
        config = CrawlConfig(
            start_url=start_url,
            strategy=CrawlStrategy(strategy),
            max_depth=max_depth,
            max_pages=max_pages,
            request_interval=interval,
            allow_domains=allow_domains,
        )
        task = CrawlTask(id=str(uuid.uuid4()), config=config)

        # 异步启动：内部使用线程执行爬取循环，避免阻塞请求
        _service.start_crawl_task(task)

        # 返回任务 ID，供前端后续查询任务状态/停止任务
        return jsonify({"task_id": task.id}), 201
    except Exception as e:
        # 统一异常处理：返回 400 与错误信息
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
