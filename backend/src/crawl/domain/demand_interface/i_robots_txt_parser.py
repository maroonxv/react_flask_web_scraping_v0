from abc import ABC, abstractmethod
from typing import Optional


class IRobotsTxtParser(ABC):
    """Robots.txt协议解析器接口"""
    
    @abstractmethod
    def is_allowed(self, url: str, user_agent: str) -> bool:
        """
        检查URL是否允许被指定user-agent爬取
        
        参数:
            url: 目标URL
            user_agent: 爬虫的User-Agent标识
            
        返回:
            True表示允许爬取，False表示禁止
            
        逻辑:
            1. 获取该域名的robots.txt文件
            2. 解析Disallow和Allow规则
            3. 判断url是否匹配禁止规则
        """
        pass
    
    @abstractmethod
    def get_crawl_delay(self, domain: str, user_agent: str) -> Optional[float]:
        """
        获取robots.txt指定的爬取延迟时间
        
        参数:
            domain: 目标域名
            user_agent: 爬虫的User-Agent
            
        返回:
            延迟秒数，None表示未指定
            
        用途:
            遵守Crawl-delay规则，避免请求过快
        """
        pass
    
    @abstractmethod
    def refresh_cache(self, domain: str) -> None:
        """
        刷新指定域名的robots.txt缓存
        
        用途:
            网站可能更新robots.txt，定期刷新缓存
        """
        pass
