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
from ..domain.demand_interface.i_crawl_repository import ICrawlRepository
from ..domain.entity.crawl_task import CrawlTask
from ..domain.value_objects.crawl_status import TaskStatus
from ..domain.value_objects.crawl_strategy import CrawlStrategy
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
        repository: ICrawlRepository,
        event_bus: Optional[EventBus] = None
    ):
        """
        构造函数注入依赖
        
        参数:
            crawl_domain_service: 爬取领域服务
            http_client: HTTP客户端
            repository: 爬取任务仓储
            event_bus: 事件总线 (可选，便于测试)
        """
        # 依赖注入：保存领域服务、HTTP客户端与URL队列引用
        self._crawl_service = crawl_domain_service
        self._http = http_client
        self._repository = repository
        self._event_bus = event_bus
        
        # 内存缓存：仅存储活跃（Running/Paused）或最近访问的任务
        # 为了简化，我们仍然可以用它来hold住对象引用，以便 queue_obj 不被回收
        self._tasks: dict[str, CrawlTask] = {}
        
        # 暂停标志
        self._paused_tasks: set[str] = set()
        self._stopped_tasks: set[str] = set()
        # 记录每个任务的工作线程
        self._threads: Dict[str, Thread] = {}

    def get_all_tasks(self) -> List[CrawlTask]:
        """获取所有任务（从数据库）"""
        return self._repository.get_all_tasks()

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
        task.url_queue_obj = UrlQueueImpl()
        
        # 存储任务到内存缓存
        self._tasks[task_id] = task
        
        # 持久化到数据库
        self._repository.save_task(task)
        
        return task_id

    def start_crawl_task(self, task_id: str) -> None:
        """
        启动爬取任务
        
        参数:
            task_id: 任务ID
        """
        # 0. 检查是否有其他任务正在运行
        # 检查内存中的活跃任务
        for t in self._tasks.values():
            if t.id != task_id and t.status == TaskStatus.RUNNING:
                raise ValueError(f"已有任务 {t.id} 正在运行，请先停止它")
        
        # 获取任务对象（优先内存，其次DB）
        task = self._tasks.get(task_id)
        if not task:
            task = self._repository.get_task(task_id)
            if task:
                # 重新初始化非持久化字段
                task.url_queue_obj = UrlQueueImpl()
                self._tasks[task_id] = task
        
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")

        # 1. 验证任务状态：仅允许从 PENDING/PAUSED 进入 RUNNING
        # 如果是从DB加载的，可能是 STOPPED/FAILED/COMPLETED，这些能不能重启？
        # 假设可以重启 STOPPED/FAILED/COMPLETED 任务，视为新的一轮（清空 visited?）
        # 或者严格遵循状态机。这里遵循严格状态机，如果想重跑，需要新建任务或重置状态。
        # 为了方便演示，允许 STOPPED/FAILED/COMPLETED 重新开始（视为 Resume or Restart）
        
        if task.status in [TaskStatus.COMPLETED, TaskStatus.STOPPED, TaskStatus.FAILED]:
             # 允许重启，但需要重置状态？或者视为 Resume?
             # 如果是 PENDING/PAUSED，正常流程。
             pass
        elif task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED]:
             raise ValueError(f"任务状态为 {task.status}，无法启动")
        
        # 2. 领域层状态转换：设置任务状态为 RUNNING/恢复
        if task.status == TaskStatus.PENDING:
            task.start_crawl()
        else:
            task.resume_crawl()
        
        # 持久化状态变更
        self._repository.save_task(task)
        
        # 发布状态变更事件
        self._publish_domain_events(task)

        # 3. 初始化队列(仅在首次启动时)
        queue = task.url_queue_obj
        if not queue:
            task.url_queue_obj = UrlQueueImpl()
            queue = task.url_queue_obj

        if task.status == TaskStatus.RUNNING and queue.is_empty():
             # 只有当队列为空（可能是新任务或意外清空）时才初始化
             
             # 如果是 Resume，且 visited_urls 不为空，但队列空了（因为没持久化队列），
             # 我们只能重新 add start_url，但 visited_urls 会阻止它被处理吗？
             # 如果 is_url_visited(start_url) 为真，它会被跳过。
             # 这是一个问题。为了演示，我们假设 Resume 主要是针对 "Pause" (内存还在)。
             # 如果是 Restart (内存丢了)，我们可能需要清空 visited_urls 才能重跑?
             # 或者我们允许 start_url 即使 visited 也可以入队?
             
             if len(task.visited_urls) == 0: 
                 # 新任务
                 queue.clear()
                 queue.initialize(
                    start_url=task.config.start_url,
                    strategy=task.config.strategy.value,
                    max_depth=task.config.max_depth
                )
             else:
                 # 可能是重启的任务。如果我们不清空 visited，队列又空，任务会立即结束。
                 # 这种情况下，我们假设用户想重跑？
                 # 或者是想继续？
                 # 简单起见，如果是从 STOPPED/FAILED/COMPLETED 重启，我们清空 visited。
                 # 如果是 PAUSED 恢复，我们保留 visited。
                 pass
        
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
            raise ValueError(f"任务 {task_id} 不存在或未在运行")
        
        # 领域层状态转换：设置为 PAUSED
        task.pause_crawl()
        self._repository.save_task(task) # 持久化
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
            # 尝试从DB加载
            task = self._repository.get_task(task_id)
            if task:
                self._tasks[task_id] = task
                task.url_queue_obj = UrlQueueImpl() # 重建队列对象（空的）
        
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        # 领域层状态转换：恢复为 RUNNING
        task.resume_crawl()
        self._repository.save_task(task) # 持久化
        self._publish_domain_events(task)
        
        # 移除暂停标志：允许循环继续
        self._paused_tasks.discard(task_id)
        
        # 检查现有线程是否存活
        # 如果旧线程还在运行（例如正在sleep中，未及响应pause就收到了resume），
        # 则不需要启动新线程，让旧线程继续运行即可，避免双线程竞争导致任务意外结束。
        existing_thread = self._threads.get(task_id)
        if existing_thread and existing_thread.is_alive():
            return

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
             # 如果内存没有，可能已经停止了，更新DB即可
             task = self._repository.get_task(task_id)
             if not task:
                 raise ValueError(f"任务 {task_id} 不存在")
        
        self._stopped_tasks.add(task_id)
        
        task.stop_crawl()
        self._repository.save_task(task) # 持久化
        self._publish_domain_events(task)
        
        if task.url_queue_obj:
            task.url_queue_obj.clear()


# -------------------- 爬取任务结果、状态查询 --------------------
    
    def get_task_results(self, task_id: str) -> List[CrawlResult]:
        """
        获取任务的最新结果列表
        """
        # 优先从 repository 获取完整结果
        # task.results 在内存中只包含本次运行新增的（如果没全加载的话）
        # 但我们之前 implementation 中 repository.get_task 没有加载 results
        # 所以我们需要调用 repository.get_results
        return self._repository.get_results(task_id)


    def get_task_status(self, task_id: str) -> dict:
        """
        获取任务状态(用于GUI显示)
        
        返回:
            任务状态字典
            - task_id/status/visited_count/result_count/queue_size/current_depth
        """
        # 优先查询内存任务（获取实时队列信息）
        task = self._tasks.get(task_id)
        is_in_memory = True
        
        if not task:
            # 内存没有，查DB
            task = self._repository.get_task(task_id)
            is_in_memory = False
            
        if not task:
            return {"error": "任务不存在"}
        
        # 获取结果数量
        # 如果在内存中，task.results 可能不全（如果我们做了分页加载优化），或者全（如果我们一直append）
        # 为了准确，查询 DB count? 或者 repository.get_results
        # 为了性能，如果内存有，用内存的长度 + 历史？
        # 目前 CrawlTask.results 是累加的。如果从DB加载，results是空的。
        # 所以如果 is_in_memory is False，results count 应该是 DB count。
        # 如果 is_in_memory is True，task.results 包含所有吗？
        # 在 _execute_crawl_loop 中，我们 task.add_crawl_result。
        # 如果任务是从 DB 加载并 resume 的，task.results 初始为空。
        # 所以 task.results 只包含 "本次运行" 的结果。
        # 这是一个 bug。我们需要 total result count。
        # 简单做法：查询 DB results count。
        # 为了避免每次查询所有结果，我们可以 add count method to repository.
        # 或者 get_results(task_id) len.
        
        results_count = len(self._repository.get_results(task_id))

        return {
            "task_id": task.id,
            "name": task.name,  # Added name
            "status": task.status.value,
            # 注意：实体中维护了去重集合 _visited_urls
            "visited_count": len(task.visited_urls),
            "result_count": results_count,
            "queue_size": task.url_queue_obj.size() if is_in_memory and task.url_queue_obj else 0,
            "current_depth": task.url_queue_obj.get_current_depth() if is_in_memory and task.url_queue_obj else 0
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
            
            # 修改：暂停时不退出循环，而是休眠等待
            # 这样可以避免线程退出后的竞态条件，确保恢复时能平滑继续
            if task.id in self._paused_tasks or task.status == TaskStatus.PAUSED:
                time.sleep(1)
                continue
            
            # 检查任务状态：确保仅在 RUNNING 期间工作
            if task.status != TaskStatus.RUNNING:
                # 如果不是 RUNNING 且不是 PAUSED (上面已处理)，那可能是 STOPPED/FAILED 等
                break
            
            # 1. 从队列取出URL：根据策略（BFS/DFS/PRIORITY）返回下一个待爬取项
            loop_start_time = time.time()
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
            tags = []
            if task.config.strategy.value == "BIG_SITE_FIRST":
                 for domain in task.config.priority_domains:
                      if domain in url:
                           tags.append("big_site")
                           # 可视化反馈：控制台日志
                           print(f"[BIG_SITE] ⭐ 正在处理优先站点: {url}")
                           break

            result = CrawlResult(
                url=url,
                title=metadata.title,
                author=metadata.author,
                abstract=metadata.abstract,
                keywords=metadata.keywords,
                publish_date=metadata.publish_date,
                pdf_links=pdf_links,
                tags=tags,
                depth=depth,
                crawled_at=datetime.now()
            )
            
            # 使用新的方法添加结果并记录事件
            task.add_crawl_result(result, depth)
            
            # 持久化结果
            self._repository.save_result(task.id, result)
            
            # 定期持久化任务状态（主要是 visited_urls）
            # 为了性能，每 5 个 URL 保存一次 task
            if len(task.visited_urls) % 5 == 0:
                self._repository.save_task(task)

            # 发布积压的事件（如PageCrawledEvent）
            self._publish_domain_events(task)

            # 供crawler_view调用：查询一次最新结果
            # latest_results = self.get_task_results(task.id)
            
            # 10. 将新发现的链接加入队列(深度+1)：可调整优先级策略
            is_big_site_mode = task.config.strategy.value == "BIG_SITE_FIRST"
            
            for link in crawlable_links:
                if not task.is_url_visited(link):
                    # 计算优先级
                    priority = 0
                    
                    # 基础优先级规则
                    if link.lower().endswith('.pdf'):
                        priority += 5  # 小站PDF
                    else:
                        priority += 1  # 普通页面
                    
                    # 大站优先策略
                    if is_big_site_mode:
                        is_priority_domain = False
                        for domain in task.config.priority_domains:
                            if domain in link:
                                is_priority_domain = True
                                break
                        
                        if is_priority_domain:
                            priority += 100 # 大站 > 小站PDF(5)
                    
                    queue.enqueue(link, depth=depth + 1, priority=priority)
            
            # 11. 请求间隔控制 (Rate Limiting)
            # 动态调整：遵守 robots.txt 的 Crawl-delay
            # 注意：使用当前请求的 url 获取对应域名的延迟
            robots_delay = self._crawl_service.get_domain_crawl_delay(url)
            
            # 取最大值 (谁更慢听谁的)
            target_interval = max(
                task.config.request_interval, 
                robots_delay if robots_delay is not None else 0
            )
            
            elapsed = time.time() - loop_start_time
            sleep_time = max(0, target_interval - elapsed)
            
            if robots_delay and robots_delay > task.config.request_interval and sleep_time > 0:
                # 仅在显著增加延迟时打印日志，避免刷屏
                print(f"[RateLimit] 遵守 robots.txt 限制 ({url}), 动态调整休眠时间为: {target_interval}s")
                
            time.sleep(sleep_time)
        
        # 12. 爬取完成或停止：根据停止标志或队列耗尽设置最终状态
        if task.id in self._stopped_tasks:
            task.stop_crawl()
        elif queue.is_empty() and task.status == TaskStatus.RUNNING:
            task.complete_crawl()
        
        # 最终持久化
        self._repository.save_task(task)
        
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
            raise ValueError(f"任务 {task_id} 不存在或未在内存中运行")
            
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
            # 尝试从DB加载
            task = self._repository.get_task(task_id)
            if task:
                self._tasks[task_id] = task

        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
            
        # 更新任务配置
        task.set_config(interval=interval, max_pages=max_pages, max_depth=max_depth)
        # 持久化
        self._repository.save_task(task)
