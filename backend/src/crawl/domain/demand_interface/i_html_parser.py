from typing import List, Dict
from abc import ABC, abstractmethod


class IHtmlParser(ABC):
    """只负责HTML结构解析，不包含业务判断"""
    
    @abstractmethod
    def extract_links(self, html: str, base_url: str) -> List[str]:
        """提取所有链接并标准化"""
        pass
    
    @abstractmethod
    def extract_meta_tags(self, html: str) -> Dict[str, str]:
        """提取所有meta标签 {"name": "content"}"""
        pass
    
    @abstractmethod
    def extract_text_content(self, html: str) -> str:
        """提取纯文本内容"""
        pass
