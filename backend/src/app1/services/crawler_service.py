"""
应用层
"""


class CrawlerService:
    def __init__(
        self,
        task_repository: ICrawlTaskRepository,
        crawl_domain_service: ICrawlDomainService,
        http_client: IHttpClient,
        url_queue: IUrlQueue,
        rate_limiter: IRateLimiter
    ):
        self._task_repo = task_repository
        self._crawl_service = crawl_domain_service
        self._http = http_client
        self._queue = url_queue
        self._limiter = rate_limiter
    
    def execute_crawl_task(self, task_id: str):
        """应用服务编排整个用例流程"""
        # 1. 加载聚合根
        task = self._task_repo.get(task_id)
        task.start()  # 聚合根方法
        
        # 2. 初始化队列
        self._queue.initialize(task.config.start_url, task.config.strategy)
        
        while not self._queue.is_empty() and task.status == TaskStatus.RUNNING:
            url = self._queue.dequeue()
            
            # 3. 聚合根业务规则检查
            if task.is_url_visited(url) or not task.is_url_in_allowed_domains(url):
                continue
            
            # 4. 领域服务业务规则检查
            if not self._crawl_service.is_url_crawlable(url, task.config.user_agent):
                continue
            
            # 5. 速率控制 (基础设施)
            self._limiter.wait_if_needed()
            
            # 6. HTTP请求 (基础设施)
            response = self._http.get(url)
            
            if response.status_code != 200:
                continue
            
            # 7. 领域服务提取元信息
            page_metadata = self._crawl_service.extract_page_metadata(url, response.content)
            
            # 8. 领域服务发现PDF链接
            pdf_links = self._crawl_service.discover_pdf_links(response.content, url)
            
            # 9. 创建结果值对象
            result = CrawlResult(
                url=url,
                metadata=page_metadata,
                pdf_links=pdf_links,
                crawled_at=datetime.now()
            )
            
            # 10. 聚合根记录状态
            task.mark_url_visited(url)
            task.add_result(result)  # 添加这个方法到聚合根
            
            # 11. 将新发现的链接加入队列
            for link in pdf_links:
                normalized_link = self._crawl_service.normalize_url(link, url)
                if not task.is_url_visited(normalized_link):
                    self._queue.enqueue(normalized_link)
        
        # 12. 完成任务
        task.complete()
        self._task_repo.save(task)
