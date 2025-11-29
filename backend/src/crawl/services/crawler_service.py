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

from datetime import datetime
from typing import Dict
from threading import Thread
from ..domain.domain_service.i_crawl_domain_service import ICrawlDomainService
from ..domain.demand_interface.i_http_client import IHttpClient
from ..domain.demand_interface.i_url_queue import IUrlQueue
from ..domain.entity.crawl_task import CrawlTask
from ..domain.value_objects.crawl_status import TaskStatus
from ..domain.value_objects.crawl_result import CrawlResult



class CrawlerService:
    """
    应用服务 - 爬取任务编排
    职责：
    - 维护任务字典与线程字典；
    - 根据任务状态初始化 URL 队列并驱动爬取循环；
    - 对外提供暂停/恢复/停止控制与状态查询接口。
    """
    
    def __init__(
        self,
        crawl_domain_service: ICrawlDomainService,
        http_client: IHttpClient,
        url_queue: IUrlQueue
    ):
        """
        构造函数注入依赖
        
        参数:
            crawl_domain_service: 爬取领域服务
            http_client: HTTP客户端
            url_queue: URL队列
        """
        # 依赖注入：保存领域服务、HTTP客户端与URL队列引用
        self._crawl_service = crawl_domain_service
        self._http = http_client
        self._queue = url_queue
        
        # 暂时用字典模拟任务存储(后续可替换为仓储)
        self._tasks: dict[str, CrawlTask] = {}
        
        # 暂停标志
        self._paused_tasks: set[str] = set()
        self._stopped_tasks: set[str] = set()
        # 记录每个任务的工作线程
        self._threads: Dict[str, Thread] = {}
    
    def start_crawl_task(self, task: CrawlTask) -> None:
        """
        启动爬取任务
        
        参数:
            task: CrawlTask聚合根实例
        """
        # 1. 验证任务状态：仅允许从 PENDING/PAUSED 进入 RUNNING
        if task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED]:
            raise ValueError(f"任务状态为 {task.status}，无法启动")
        
        # 2. 领域层状态转换：设置任务状态为 RUNNING/恢复
        if task.status == TaskStatus.PENDING:
            task.start_crawl()
        else:
            task.resume_crawl()
        
        # 3. 存储任务引用：便于后续控制与查询
        self._tasks[task.id] = task
        
        # 4. 初始化队列(仅在首次启动时)：用起始URL与策略填充队列
        if task.status == TaskStatus.RUNNING and not self._queue.size():
            self._queue.initialize(
                start_url=task.config.start_url,
                strategy=task.config.strategy.value,  # 假设strategy是Enum
                max_depth=task.config.max_depth
            )
        
        # 5. 异步开始爬取循环：开启守护线程，避免阻塞调用方
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
        
        # 标记为暂停：让循环检测到后退出
        self._paused_tasks.add(task_id)
        
        print(f"任务 {task_id} 已暂停，当前队列剩余 {self._queue.size()} 个URL")
    
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
        
        # 移除暂停标志：允许循环继续
        self._paused_tasks.discard(task_id)
        
        print(f"任务 {task_id} 已恢复，继续爬取...")
        
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
        self._queue.clear()
    
    def _execute_crawl_loop(self, task: CrawlTask) -> None:
        """
        执行爬取循环
        
        参数:
            task: CrawlTask聚合根
        """
        while not self._queue.is_empty():
            # 检查是否被暂停/停止：优先响应外部控制
            if task.id in self._stopped_tasks:
                print(f"任务 {task.id} 检测到停止信号，结束爬取")
                break
            if task.id in self._paused_tasks:
                print(f"任务 {task.id} 检测到暂停信号，停止爬取")
                break
            
            # 检查任务状态：确保仅在 RUNNING 期间工作
            if task.status != TaskStatus.RUNNING:
                break
            
            # 1. 从队列取出URL：根据策略（BFS/DFS/PRIORITY）返回下一个待爬取项
            queued_url = self._queue.dequeue()
            if not queued_url:
                break
            
            url = queued_url.url
            depth = queued_url.depth
            
            print(f"正在爬取: {url} (深度: {depth}, 队列剩余: {self._queue.size()})")
            
            # 2. 聚合根业务规则 - URL去重：避免重复请求
            if task.is_url_visited(url):
                continue
            
            # 3. 聚合根业务规则 - 域名白名单：不在 allow_domains 列表则跳过
            if not task.is_url_allowed(url):
                print(f"  ✗ URL不在允许的域名列表中: {url}")
                continue
            
            # 4. 执行HTTP请求：包含重试/编码检测/错误处理
            response = self._http.get(url)
            if not response.is_success:
                print(f"  ✗ 请求失败: {response.error_message}")
                continue
            
            # 5. 领域服务 - 提取页面元信息：标题/作者/摘要/关键词/发布日期
            try:
                metadata = self._crawl_service.extract_page_metadata(response.content, url)
                print(f"  ✓ 提取元信息: {metadata.title}")
            except Exception as e:
                print(f"  ✗ 元信息提取失败: {str(e)}")
                continue
            
            # 6. 领域服务 - 发现可爬取的链接：去重/白名单/robots 检查
            try:
                crawlable_links = self._crawl_service.discover_crawlable_links(
                    response.content, url, task
                )
                print(f"  ✓ 发现 {len(crawlable_links)} 个可爬取链接")
            except Exception as e:
                print(f"  ✗ 链接提取失败: {str(e)}")
                crawlable_links = []
            
            # 7. 领域服务 - 识别PDF链接：扩展名 + HEAD Content-Type 校验
            try:
                pdf_links = self._crawl_service.identify_pdf_links(crawlable_links)
                if pdf_links:
                    print(f"  ✓ 发现 {len(pdf_links)} 个PDF链接")
            except Exception as e:
                print(f"  ✗ PDF识别失败: {str(e)}")
                pdf_links = []
            
            # 8. 更新聚合根状态：记录已访问URL
            task.mark_url_visited(url)
            
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
            task.results.append(result)
            
            # 10. 将新发现的链接加入队列(深度+1)：可调整优先级策略
            for link in crawlable_links:
                if not task.is_url_visited(link):
                    # 计算优先级(示例: PDF链接优先级更高)
                    priority = 10 if link.endswith('.pdf') else 5
                    self._queue.enqueue(link, depth=depth + 1, priority=priority)
        
        # 11. 爬取完成或停止：根据停止标志或队列耗尽设置最终状态
        if task.id in self._stopped_tasks:
            task.stop_crawl()
        elif self._queue.is_empty() and task.status == TaskStatus.RUNNING:
            task.complete_crawl()
            print(f"任务 {task.id} 完成! 共爬取 {len(task.results)} 个页面")
    
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
            "status": task.status.value,
            # 注意：实体中维护了去重集合 _visited_urls
            "visited_count": len(task.visited_urls),
            "result_count": len(task.results),
            "queue_size": self._queue.size(),
            "current_depth": self._queue.get_current_depth()
        }




