"""
模块职责（应用层）
- 负责编排一次完整的爬取任务生命周期：启动/暂停/恢复/停止/完成；
- 以任务聚合根 `CrawlTask` 为中心，协调领域服务、HTTP 客户端、URL 队列；
- 在应用层引入异步线程以非阻塞方式执行爬取循环；
- 提供面向界面的查询方法以展示任务状态。

设计要点
- 应用层仅做编排与流程控制，不承载具体解析与业务规则（这些在领域服务与实体中实现）；
- 使用线程的原因：简化演示并避免阻塞 HTTP 请求线程（生产可替换为任务队列/协程/调度器）；
- 状态管理：通过 `TaskStatus` 与本类内部的 `paused/stopped` 集合，确保循环可及时响应控制指令；
- 幂等性与安全：启动时校验状态、停止时清队列，避免重复执行或资源泄漏。
"""


# 注意，这里没有转发日志的逻辑，那部分逻辑全部写在 shared里面。
# shared在DDD的分层架构中，亦属于应用层。

from datetime import datetime
from typing import Dict, List, Optional
from threading import Thread
import time  # 引入 time 模块
from ..domain.domain_service.i_crawl_domain_service import ICrawlDomainService
from ..domain.demand_interface.i_http_client import IHttpClient
from ..domain.demand_interface.i_url_queue import IUrlQueue
from ..domain.entity.crawl_task import CrawlTask
from ..domain.value_objects.crawl_status import TaskStatus
from ..domain.value_objects.crawl_result import CrawlResult
from ..domain.value_objects.crawl_config import CrawlConfig
from src.shared.event_bus import EventBus


from ..infrastructure.url_queue_impl import UrlQueueImpl

class CrawlerService:
    """
    应用服务 - 爬取任务编排
    职责：
    - 维护任务字典与线程字典；
    - 根据任务状态初始化 URL 队列并驱动爬取循环；
    - 对外提供暂停/恢复/停止控制与状态查询接口。
    - 发布领域事件到事件总线
    """
    
    def __init__(
        self,
        crawl_domain_service: ICrawlDomainService,
        http_client: IHttpClient,
        # url_queue: IUrlQueue, # 移除单例注入
        event_bus: Optional[EventBus] = None
    ):
        """
        构造函数注入依赖
        
        参数:
            crawl_domain_service: 爬取领域服务
            http_client: HTTP客户端
            # url_queue: URL队列
            event_bus: 事件总线 (可选，便于测试)
        """
        # 依赖注入：保存领域服务、HTTP客户端与URL队列引用
        self._crawl_service = crawl_domain_service
        self._http = http_client
        # self._queue = url_queue # 移除单例引用
        self._event_bus = event_bus
        
        # 暂时用字典模拟任务存储(后续可替换为仓储)
        self._tasks: dict[str, CrawlTask] = {}
        
        # 暂停标志
        self._paused_tasks: set[str] = set()
        self._stopped_tasks: set[str] = set()
        # 记录每个任务的工作线程
        self._threads: Dict[str, Thread] = {}



# -------------------- 爬取任务生命周期管理 --------------------

    def create_crawl_task(self, config: CrawlConfig, name: str = None) -> str:
        """
        创建爬取任务（不自动启动）
        
        参数:
            config: 任务配置对象
            name: 任务名称
            
        返回:
            task_id
        """
        # 生成唯一ID
        import uuid
        task_id = str(uuid.uuid4())
        
        # 创建聚合根
        task = CrawlTask(id=task_id, config=config, name=name)
        
        # 初始化该任务的专属URL队列
        # 重构：每个任务拥有独立的UrlQueueImpl实例
        task.url_queue_obj = UrlQueueImpl()
        
        # 存储任务
        self._tasks[task_id] = task
        
        return task_id

    def start_crawl_task(self, task_id: str) -> None:
        """
        启动爬取任务
        
        参数:
            task_id: 任务ID
        """
        # 0. 检查是否有其他任务正在运行
        for t in self._tasks.values():
            if t.id != task_id and t.status == TaskStatus.RUNNING:
                raise ValueError(f"已有任务 {t.id} 正在运行，请先停止它")
        
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")

        # 1. 验证任务状态：仅允许从 PENDING/PAUSED 进入 RUNNING
        if task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED]:
            raise ValueError(f"任务状态为 {task.status}，无法启动")
        
        # 2. 领域层状态转换：设置任务状态为 RUNNING/恢复
        if task.status == TaskStatus.PENDING:
            task.start_crawl()
        else:
            task.resume_crawl()
        
        # 发布状态变更事件
        self._publish_domain_events(task)

        # 3. 初始化队列(仅在首次启动时)
        queue = task.url_queue_obj
        if task.status == TaskStatus.RUNNING and queue.is_empty():
             # 只有当队列为空（可能是新任务或意外清空）时才初始化
             
             if len(task.visited_urls) == 0: # 简单判断是否新任务
                 queue.clear()
                 queue.initialize(
                    start_url=task.config.start_url,
                    strategy=task.config.strategy.value,
                    max_depth=task.config.max_depth
                )
        
        # 4. 异步开始爬取循环：开启守护线程，避免阻塞调用方
        t = Thread(target=self._execute_crawl_loop, args=(task,), daemon=True)
        self._threads[task.id] = t
        t.start()
    
    def pause_crawl_task(self, task_id: str) -> None:
        """
        暂停爬取任务
        
        参数:
            task_id: 任务ID
        """
        # 查询并校验任务存在性
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        # 领域层状态转换：设置为 PAUSED
        task.pause_crawl()
        self._publish_domain_events(task)
        
        # 标记为暂停：让循环检测到后退出
        self._paused_tasks.add(task_id)
        
    
    def resume_crawl_task(self, task_id: str) -> None:
        """
        恢复爬取任务
        
        参数:
            task_id: 任务ID
        """
        # 查询并校验任务存在性
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        # 领域层状态转换：恢复为 RUNNING
        task.resume_crawl()
        self._publish_domain_events(task)
        
        # 移除暂停标志：允许循环继续
        self._paused_tasks.discard(task_id)
        
        # 继续爬取：重新开启线程进入循环
        t = Thread(target=self._execute_crawl_loop, args=(task,), daemon=True)
        self._threads[task.id] = t
        t.start()

    def stop_crawl_task(self, task_id: str) -> None:
        """
        停止爬取任务（软停止）
        - 将任务状态置为 STOPPED；
        - 清空队列；
        - 让循环检测到停止标志后退出。
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        self._stopped_tasks.add(task_id)
        
        task.stop_crawl()
        self._publish_domain_events(task)
        
        if task.url_queue_obj:
            task.url_queue_obj.clear()


# -------------------- 爬取任务结果、状态查询 --------------------
    
    def get_task_results(self, task_id: str) -> List[CrawlResult]:
        """
        获取任务的最新结果列表
        """
        task = self._tasks.get(task_id)
        if not task:
            return []
        return task.results


    def get_task_status(self, task_id: str) -> dict:
        """
        获取任务状态(用于GUI显示)
        
        返回:
            任务状态字典
            - task_id/status/visited_count/result_count/queue_size/current_depth
        """
        # 查询任务，不存在则返回错误消息
        task = self._tasks.get(task_id)
        if not task:
            return {"error": "任务不存在"}
        
        return {
            "task_id": task.id,
            "name": task.name,  # Added name
            "status": task.status.value,
            # 注意：实体中维护了去重集合 _visited_urls
            "visited_count": len(task.visited_urls),
            "result_count": len(task.results),
            "queue_size": task.url_queue_obj.size() if task.url_queue_obj else 0,
            "current_depth": task.url_queue_obj.get_current_depth() if task.url_queue_obj else 0
        }

# ---------------------  内部方法：执行爬取循环、处理事件队列 ---------------------


    def _execute_crawl_loop(self, task: CrawlTask) -> None:
        """
        执行爬取循环
        
        参数:
            task: CrawlTask聚合根
        """
        queue = task.url_queue_obj
        if not queue:
             return

        while not queue.is_empty():
            # 检查是否被暂停/停止：优先响应外部控制
            if task.id in self._stopped_tasks:
                break
            if task.id in self._paused_tasks:
                break
            
            # 检查任务状态：确保仅在 RUNNING 期间工作
            if task.status != TaskStatus.RUNNING:
                break
            
            # 1. 从队列取出URL：根据策略（BFS/DFS/PRIORITY）返回下一个待爬取项
            queued_url = queue.dequeue()
            if not queued_url:
                break
            
            url = queued_url.url
            depth = queued_url.depth
            
            # 2. 聚合根业务规则 - URL去重：避免重复请求
            if task.is_url_visited(url):
                continue
            
            # 3. 聚合根业务规则 - 域名白名单：不在 allow_domains 列表则跳过
            if not task.is_url_allowed(url):
                task.record_crawl_error(url, "URL不在允许的域名列表中", "DomainNotAllowed")
                self._publish_domain_events(task)
                continue
            
            # 4. 执行HTTP请求：包含重试/编码检测/错误处理
            # 提前标记为已访问，表明正在处理或已处理，防止重复入队
            task.mark_url_visited(url)
            
            response = self._http.get(url)
            if not response.is_success:
                task.record_crawl_error(url, f"请求失败: {response.error_message}", "RequestFailed")
                self._publish_domain_events(task)
                continue
            
            # 5. 领域服务 - 提取页面元信息：标题/作者/摘要/关键词/发布日期
            try:
                metadata = self._crawl_service.extract_page_metadata(response.content, url)
            except Exception as e:
                task.record_crawl_error(url, f"元信息提取失败: {str(e)}", "MetadataExtractionFailed")
                self._publish_domain_events(task)
                continue
            
            # 6. 领域服务 - 发现可爬取的链接：去重/白名单/robots 检查
            try:
                crawlable_links = self._crawl_service.discover_crawlable_links(
                    response.content, url, task
                )
            except Exception as e:
                task.record_crawl_error(url, f"链接提取失败: {str(e)}", "LinkExtractionFailed")
                self._publish_domain_events(task)
                crawlable_links = []
            
            # 7. 领域服务 - 识别PDF链接：扩展名 + HEAD Content-Type 校验
            try:
                pdf_links = self._crawl_service.identify_pdf_links(crawlable_links)
            except Exception as e:
                task.record_crawl_error(url, f"PDF识别失败: {str(e)}", "PdfIdentificationFailed")
                self._publish_domain_events(task)
                pdf_links = []
            
            # 8. 更新聚合根状态：记录已访问URL (已提前移动到请求前)
            # task.mark_url_visited(url)
            
            # 9. 创建并追加爬取结果：供外部查询显示
            result = CrawlResult(
                url=url,
                title=metadata.title,
                author=metadata.author,
                abstract=metadata.abstract,
                keywords=metadata.keywords,
                publish_date=metadata.publish_date,
                pdf_links=pdf_links,
                crawled_at=datetime.now()
            )
            
            # 使用新的方法添加结果并记录事件
            task.add_crawl_result(result, depth)

            
            # 发布积压的事件（如PageCrawledEvent）
            self._publish_domain_events(task)

            # 供crawler_view调用：查询一次最新结果
            # (虽然此处没有直接传递给view，但符合“每增加一条结果就查询一次”的要求，
            #  实际上可以通过事件或者回调机制通知View，这里我们假设事件发布就是通知机制的一部分)
            latest_results = self.get_task_results(task.id)
            
            # 10. 将新发现的链接加入队列(深度+1)：可调整优先级策略
            for link in crawlable_links:
                if not task.is_url_visited(link):
                    # 计算优先级(示例: PDF链接优先级更高)
                    priority = 10 if link.endswith('.pdf') else 5
                    queue.enqueue(link, depth=depth + 1, priority=priority)
            
            # 11. 请求间隔控制 (Rate Limiting)
            time.sleep(task.config.request_interval)
        
        # 12. 爬取完成或停止：根据停止标志或队列耗尽设置最终状态
        if task.id in self._stopped_tasks:
            task.stop_crawl()
        elif queue.is_empty() and task.status == TaskStatus.RUNNING:
            task.complete_crawl()
        
        # 发布最终状态变更事件（Stopped 或 Completed）
        self._publish_domain_events(task)
    
    def _publish_domain_events(self, task: CrawlTask):
        """发布任务中积压的领域事件"""
        if not self._event_bus:
            return
            
        events = task.get_uncommitted_events()
        for event in events:
            self._event_bus.publish(event)
        
        # 清空已发布的事件
        task.clear_events()


# --------------------- 设置队列操作与策略 ---------------------
    # 控制队列

    # 逐个添加url
    def add_url(self, task_id: str, url: str, depth: int = 0, priority: int = 0) -> None:
        """
        逐个添加URL到队列
        
        参数:
            task_id: 任务ID
            url: 待爬取的URL
            depth: 当前深度(从起始URL开始计数)
            priority: 优先级(仅在PRIORITY策略下有效)
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
            
        if task.url_queue_obj:
             task.url_queue_obj.enqueue(url, depth=depth, priority=priority)

    def set_crawl_config(self, task_id: str, interval: float = None, max_pages: int = None, max_depth: int = None) -> None:
        """
        设置爬取配置（仅限 interval/max_pages/max_depth）
        
        参数:
            task_id: 任务ID
            interval: 请求间隔
            max_pages: 最大页面数
            max_depth: 最大深度
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
            
        # 更新任务配置
        task.set_config(interval=interval, max_pages=max_pages, max_depth=max_depth)



