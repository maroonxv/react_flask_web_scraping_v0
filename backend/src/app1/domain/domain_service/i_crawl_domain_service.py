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
    def extract_page_metadata(self, url: str, html_content: str) -> PageMetadata:
        """
        从HTML页面中提取元信息
        返回: PageMetadata(title, author, abstract, keywords, publish_date, url)
        领域逻辑: 确定优先使用哪些HTML标签（Open Graph vs meta标签）
        """
        pass
    
    @abstractmethod
    def discover_pdf_links(self, html_content: str, base_url: str) -> List[str]:
        """
        从HTML中发现所有PDF链接
        返回: 标准化的PDF URL列表
        领域逻辑: 判断哪些链接指向PDF（扩展名、MIME类型、链接文本）
        """
        pass
    
    @abstractmethod
    def is_url_crawlable(self, url: str, user_agent: str) -> bool:
        """
        判断URL是否允许爬取
        领域逻辑: 综合robots.txt规则和业务规则
        """
        pass
    
    @abstractmethod
    def normalize_url(self, url: str, base_url: str) -> str:
        """
        URL标准化
        领域逻辑: 去除fragment、统一协议、处理相对路径
        """
        pass
