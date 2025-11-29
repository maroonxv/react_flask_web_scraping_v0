"""
应用层
"""

from datetime import datetime
from typing import Dict
from crawl.domain.domain_service.i_crawl_domain_service import ICrawlDomainService
from crawl.domain.demand_interface.i_http_client import IHttpClient
from crawl.domain.demand_interface.i_url_queue import IUrlQueue
from crawl.domain.entity.crawl_task import CrawlTask
from crawl.domain.value_objects.crawl_status import TaskStatus
from crawl.domain.value_objects.crawl_result import CrawlResult


        # 1. 直接使用IHttpClient获取内容
        # 2. 使用领域服务提取元信息（包含业务逻辑）
        # 3. 使用领域服务发现可爬取链接（包含过滤规则）
        # 4. 使用领域服务识别PDF链接
        # 5. 保存结果
        # 6. 加入队列

class CrawlerService:
    """
    应用服务 - 爬取任务编排
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
        self._crawl_service = crawl_domain_service
        self._http = http_client
        self._queue = url_queue
        
        # 暂时用字典模拟任务存储(后续用repository替换)
        self._tasks: dict[str, CrawlTask] = {}
        
        # 暂停标志
        self._paused_tasks: set[str] = set()
    
    def start_crawl_task(self, task: CrawlTask) -> None:
        """
        启动爬取任务
        
        参数:
            task: CrawlTask聚合根实例
        """
        # 1. 验证任务状态
        if task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED]:
            raise ValueError(f"任务状态为 {task.status}，无法启动")
        
        # 2. 领域层状态转换
        if task.status == TaskStatus.PENDING:
            task.start_crawl()
        else:
            task.resume_crawl()
        
        # 3. 存储任务引用
        self._tasks[task.id] = task
        
        # 4. 初始化队列(仅在首次启动时)
        if task.status == TaskStatus.RUNNING and not self._queue.size():
            self._queue.initialize(
                start_url=task.config.start_url,
                strategy=task.config.strategy.value,  # 假设strategy是Enum
                max_depth=task.config.max_depth
            )
        
        # 5. 开始爬取循环
        self._execute_crawl_loop(task)
    
    def pause_crawl_task(self, task_id: str) -> None:
        """
        暂停爬取任务
        
        参数:
            task_id: 任务ID
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        # 领域层状态转换
        task.pause_crawl()
        
        # 标记为暂停
        self._paused_tasks.add(task_id)
        
        print(f"任务 {task_id} 已暂停，当前队列剩余 {self._queue.size()} 个URL")
    
    def resume_crawl_task(self, task_id: str) -> None:
        """
        恢复爬取任务
        
        参数:
            task_id: 任务ID
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        # 领域层状态转换
        task.resume_crawl()
        
        # 移除暂停标志
        self._paused_tasks.discard(task_id)
        
        print(f"任务 {task_id} 已恢复，继续爬取...")
        
        # 继续爬取
        self._execute_crawl_loop(task)
    
    def _execute_crawl_loop(self, task: CrawlTask) -> None:
        """
        执行爬取循环
        
        参数:
            task: CrawlTask聚合根
        """
        while not self._queue.is_empty():
            # 检查是否被暂停
            if task.id in self._paused_tasks:
                print(f"任务 {task.id} 检测到暂停信号，停止爬取")
                break
            
            # 检查任务状态
            if task.status != TaskStatus.RUNNING:
                break
            
            # 1. 从队列取出URL
            queued_url = self._queue.dequeue()
            if not queued_url:
                break
            
            url = queued_url.url
            depth = queued_url.depth
            
            print(f"正在爬取: {url} (深度: {depth}, 队列剩余: {self._queue.size()})")
            
            # 2. 聚合根业务规则 - URL去重
            if task.is_url_visited(url):
                continue
            
            # 3. 聚合根业务规则 - 域名白名单
            if not task.is_url_allowed(url):
                print(f"  ✗ URL不在允许的域名列表中: {url}")
                continue
            
            # 4. 执行HTTP请求
            response = self._http.get(url)
            if not response.is_success:
                print(f"  ✗ 请求失败: {response.error_message}")
                continue
            
            # 5. 领域服务 - 提取页面元信息
            try:
                metadata = self._crawl_service.extract_page_metadata(response.content, url)
                print(f"  ✓ 提取元信息: {metadata.title}")
            except Exception as e:
                print(f"  ✗ 元信息提取失败: {str(e)}")
                continue
            
            # 6. 领域服务 - 发现可爬取的链接
            try:
                crawlable_links = self._crawl_service.discover_crawlable_links(
                    response.content, url, task
                )
                print(f"  ✓ 发现 {len(crawlable_links)} 个可爬取链接")
            except Exception as e:
                print(f"  ✗ 链接提取失败: {str(e)}")
                crawlable_links = []
            
            # 7. 领域服务 - 识别PDF链接
            try:
                pdf_links = self._crawl_service.identify_pdf_links(crawlable_links)
                if pdf_links:
                    print(f"  ✓ 发现 {len(pdf_links)} 个PDF链接")
            except Exception as e:
                print(f"  ✗ PDF识别失败: {str(e)}")
                pdf_links = []
            
            # 8. 更新聚合根状态
            task.mark_url_visited(url)
            
            # 创建爬取结果
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
            
            # 9. 将新发现的链接加入队列(深度+1)
            for link in crawlable_links:
                if not task.is_url_visited(link):
                    # 计算优先级(示例: PDF链接优先级更高)
                    priority = 10 if link.endswith('.pdf') else 5
                    self._queue.enqueue(link, depth=depth + 1, priority=priority)
        
        # 10. 爬取完成
        if self._queue.is_empty() and task.status == TaskStatus.RUNNING:
            task.complete_crawl()
            print(f"任务 {task.id} 完成! 共爬取 {len(task.results)} 个页面")
    
    def get_task_status(self, task_id: str) -> dict:
        """
        获取任务状态(用于GUI显示)
        
        返回:
            任务状态字典
        """
        task = self._tasks.get(task_id)
        if not task:
            return {"error": "任务不存在"}
        
        return {
            "task_id": task.id,
            "status": task.status.value,
            "visited_count": len(task.visited_urls),
            "result_count": len(task.results),
            "queue_size": self._queue.size(),
            "current_depth": self._queue.get_current_depth()
        }




