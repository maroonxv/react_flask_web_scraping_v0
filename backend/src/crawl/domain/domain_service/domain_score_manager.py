from typing import Dict, Set, List
from urllib.parse import urlparse
import logging

logger = logging.getLogger('domain.crawl_process')

class DomainScoreManager:
    """
    域名评分管理器 (领域服务)
    职责：
    - 维护各域名的动态权重分数 (Domain Score)
    - 提供分数的查询与更新接口
    - 结合黑白名单进行最终分数计算
    """
    
    def __init__(self, task_id: str, whitelist: List[str] = None, blacklist: List[str] = None):
        self.task_id = task_id
        self._scores: Dict[str, float] = {}  # 存储域名 -> 分数
        self._whitelist: Set[str] = set(whitelist) if whitelist else set()
        self._blacklist: Set[str] = set(blacklist) if blacklist else set()
        
        # 默认分数值
        self.DEFAULT_SCORE = 1.0
        self.MAX_SCORE = 5.0
        self.MIN_SCORE = 0.1

    def get_score(self, url: str) -> float:
        """根据 URL 获取其域名的当前权重分数"""
        domain = self._extract_domain(url)
        
        # 1. 黑白名单具有绝对优先级
        if self._is_subdomain_of_any(domain, self._whitelist):
            return 10.0  # 白名单最高分
        
        if self._is_subdomain_of_any(domain, self._blacklist):
            return 0.0   # 黑名单零分
            
        # 2. 返回动态分数，若无记录则返回默认值
        return self._scores.get(domain, self.DEFAULT_SCORE)

    def update_score(self, url: str, event_type: str) -> None:
        """
        根据发生的事件类型，调整对应域名的分数
        
        event_type 枚举:
        - RESOURCE_FOUND: 发现高价值资源 (+0.2)
        - HIGH_QUALITY_CONTENT: 内容质量高 (+0.05)
        - FAST_RESPONSE: 响应速度快 (+0.02)
        - ERROR_4XX_5XX: 访问错误 (-0.5)
        - DUPLICATE_CONTENT: 内容重复 (-0.1)
        """
        domain = self._extract_domain(url)
        
        # 如果在黑白名单中，不动态调整
        if self._is_subdomain_of_any(domain, self._whitelist) or \
           self._is_subdomain_of_any(domain, self._blacklist):
            return

        current_score = self._scores.get(domain, self.DEFAULT_SCORE)
        delta = 0.0
        
        if event_type == "RESOURCE_FOUND":
            delta = 0.2
        elif event_type == "HIGH_QUALITY_CONTENT":
            delta = 0.05
        elif event_type == "FAST_RESPONSE":
            delta = 0.02
        elif event_type == "ERROR_4XX_5XX":
            delta = -0.5
        elif event_type == "DUPLICATE_CONTENT":
            delta = -0.1
            
        # 计算新分数并限制范围
        new_score = current_score + delta
        new_score = max(self.MIN_SCORE, min(self.MAX_SCORE, new_score))
        
        self._scores[domain] = new_score
        
        # 打印日志观察权重变化 (只要变化就打印)
        if abs(delta) > 0: 
            # 翻译事件类型为中文
            event_type_cn = {
                "RESOURCE_FOUND": "发现高价值资源",
                "HIGH_QUALITY_CONTENT": "内容质量高",
                "FAST_RESPONSE": "响应速度快",
                "ERROR_4XX_5XX": "访问错误",
                "DUPLICATE_CONTENT": "内容重复"
            }.get(event_type, event_type)

            logger.info(
                f"[ScoreManager] 域名 {domain} 权重更新: {current_score:.2f} -> {new_score:.2f} ({event_type_cn})",
                extra={'task_id': self.task_id}
            )

    def _extract_domain(self, url: str) -> str:
        """从 URL 提取域名 (netloc)"""
        try:
            return urlparse(url).netloc
        except Exception:
            return ""

    def _is_subdomain_of_any(self, domain: str, domain_set: Set[str]) -> bool:
        """检查 domain 是否是 domain_set 中任意一项的子域名或相同"""
        for d in domain_set:
            if domain == d or domain.endswith("." + d):
                return True
        return False
