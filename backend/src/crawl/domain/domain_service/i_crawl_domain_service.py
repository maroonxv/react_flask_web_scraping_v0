"""
以下这些写在领域服务的原因：
1. 无法归属单个实体: extract_page_metadata涉及HTML解析和业务规则，不属于CrawlTask
2. 跨多个领域概念: is_url_crawlable需要协调robots.txt规则+任务配置+URL验证
3. 使用领域语言: discover_pdf_links而非parse_html_for_pdfs
4. 无状态: 所有方法都是纯函数，不维护内部状态​
"""



class ICrawlDomainService(ABC):
    """
    爬取领域服务 - 封装复杂的领域操作
    特点: 无状态、纯领域逻辑、使用领域语言命名
    """
    
    @abstractmethod
    def extract_page_metadata(self, html: str, url: str) -> PageMetadata:
        """
        从HTML提取业务元信息
        领域逻辑: 
        - 优先级规则(Open Graph > Twitter Card > meta > title)
        - 默认值策略(缺少字段时如何处理)
        - 日期格式解析和验证
        """
        pass
    
    @abstractmethod
    def discover_crawlable_links(self, html: str, base_url: str, task: CrawlTask) -> List[str]:
        """
        发现可爬取的链接
        领域逻辑:
        - 过滤掉已访问的URL (使用task.is_url_visited)
        - 应用域名白名单 (使用task.is_url_in_allowed_domains)
        - 检查robots.txt规则
        - URL规范化和去重
        返回: 符合爬取规则的链接列表
        """
        pass
    
    @abstractmethod
    def identify_pdf_links(self, links: List[str]) -> List[str]:
        """
        识别PDF链接
        领域逻辑:
        - .pdf扩展名判断
        - 通过HEAD请求检查Content-Type
        - 排除查询参数中的伪PDF链接
        """
        pass
