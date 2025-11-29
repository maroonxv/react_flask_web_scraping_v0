# infrastructure/robots/robots_parser_impl.py
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from typing import Optional, Dict
from ..domain.demand_interface.i_robots_txt_parser import IRobotsTxtParser


class RobotsTxtParserImpl(IRobotsTxtParser):
    """基于urllib.robotparser的实现"""
    
    def __init__(self, cache_timeout: int = 3600):
        """
        初始化
        
        参数:
            cache_timeout: robots.txt缓存时间(秒)，默认1小时
        """
        self._cache: Dict[str, RobotFileParser] = {}
        self._cache_timeout = cache_timeout
    
    def is_allowed(self, url: str, user_agent: str) -> bool:
        """检查URL是否允许爬取"""
        try:
            parsed = urlparse(url)
            domain = f"{parsed.scheme}://{parsed.netloc}"
            
            # 获取或创建该域名的robots解析器
            robot_parser = self._get_parser(domain)
            
            # 判断是否允许访问
            return robot_parser.can_fetch(user_agent, url)
        
        except Exception as e:
            # 如果robots.txt获取失败，默认允许访问
            print(f"Robots.txt解析失败: {str(e)}, 默认允许访问")
            return True
    
    def get_crawl_delay(self, domain: str, user_agent: str) -> Optional[float]:
        """获取爬取延迟"""
        try:
            robot_parser = self._get_parser(domain)
            delay = robot_parser.crawl_delay(user_agent)
            return float(delay) if delay else None
        except:
            return None
    
    def refresh_cache(self, domain: str) -> None:
        """刷新缓存"""
        if domain in self._cache:
            del self._cache[domain]
    
    def _get_parser(self, domain: str) -> RobotFileParser:
        """获取或创建robots.txt解析器"""
        if domain not in self._cache:
            robots_url = urljoin(domain, '/robots.txt')
            parser = RobotFileParser()
            parser.set_url(robots_url)
            
            try:
                parser.read()  # 下载并解析robots.txt
                self._cache[domain] = parser
            except Exception as e:
                # 创建一个允许所有访问的默认解析器
                print(f"无法获取robots.txt from {robots_url}: {str(e)}")
                parser = RobotFileParser()
                parser.parse([])  # 空规则=允许所有
                self._cache[domain] = parser
        
        return self._cache[domain]
