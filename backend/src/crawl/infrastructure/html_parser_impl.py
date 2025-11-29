# infrastructure/html/html_parser_impl.py
from typing import List, Dict
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
import re

from ..domain.demand_interface.i_html_parser import IHtmlParser


class HtmlParserImpl(IHtmlParser):
    """基于BeautifulSoup的HTML解析器实现"""
    
    def __init__(self, parser: str = 'html.parser'):
        """
        初始化HTML解析器
        
        参数:
            parser: 解析器类型，可选值:
                   'html.parser' (Python内置，默认)
                   'lxml' (更快，需安装lxml)
                   'html5lib' (最宽容，需安装html5lib)
        """
        self._parser = parser
    
    def extract_links(self, html: str, base_url: str) -> List[str]:
        """
        提取所有链接并标准化为绝对URL
        
        参数:
            html: HTML内容
            base_url: 页面基础URL，用于转换相对路径
            
        返回:
            标准化后的绝对URL列表（去重）
        """
        if not html or not base_url:
            return []
        
        try:
            soup = BeautifulSoup(html, self._parser)
            links = set()  # 使用set自动去重
            
            # 提取所有<a>标签的href属性
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()
                
                # 过滤无效链接
                if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    continue
                
                # 转换为绝对URL
                absolute_url = urljoin(base_url, href)
                
                # 标准化URL
                normalized_url = self._normalize_url(absolute_url)
                
                if normalized_url:
                    links.add(normalized_url)
            
            return list(links)
        
        except Exception as e:
            # 解析失败返回空列表，不抛出异常
            print(f"HTML链接提取失败: {str(e)}")
            return []
    
    def extract_meta_tags(self, html: str) -> Dict[str, str]:
        """
        提取所有meta标签
        
        参数:
            html: HTML内容
            
        返回:
            字典格式 {meta_name: content}
            包括标准meta、Open Graph、Twitter Card等
        """
        if not html:
            return {}
        
        try:
            soup = BeautifulSoup(html, self._parser)
            meta_data = {}
            
            # 1. 提取标准meta标签 (name属性)
            for meta in soup.find_all('meta', attrs={'name': True, 'content': True}):
                name = meta['name'].lower().strip()
                content = meta['content'].strip()
                if name and content:
                    meta_data[name] = content
            
            # 2. 提取Open Graph标签 (property="og:xxx")
            for meta in soup.find_all('meta', attrs={'property': True, 'content': True}):
                property_name = meta['property'].lower().strip()
                content = meta['content'].strip()
                if property_name and content:
                    meta_data[property_name] = content
            
            # 3. 提取Twitter Card标签 (name="twitter:xxx")
            # (已包含在第1步中)
            
            # 4. 提取<title>标签
            title_tag = soup.find('title')
            if title_tag and title_tag.string:
                meta_data['title'] = title_tag.string.strip()
            
            # 5. 提取charset编码信息
            charset_meta = soup.find('meta', attrs={'charset': True})
            if charset_meta:
                meta_data['charset'] = charset_meta['charset']
            
            return meta_data
        
        except Exception as e:
            print(f"Meta标签提取失败: {str(e)}")
            return {}
    
    def extract_text_content(self, html: str) -> str:
        """
        提取纯文本内容（去除HTML标签）
        
        参数:
            html: HTML内容
            
        返回:
            纯文本字符串，去除多余空白
        """
        if not html:
            return ""
        
        try:
            soup = BeautifulSoup(html, self._parser)
            
            # 移除script和style标签
            for script in soup(['script', 'style', 'noscript']):
                script.decompose()
            
            # 获取文本
            text = soup.get_text(separator=' ', strip=True)
            
            # 清理多余空白
            text = re.sub(r'\s+', ' ', text)
            
            return text.strip()
        
        except Exception as e:
            print(f"文本内容提取失败: {str(e)}")
            return ""
    
    def _normalize_url(self, url: str) -> str:
        """
        标准化URL
        
        处理:
            - 去除fragment (#部分)
            - 统一协议为小写
            - 去除默认端口
            - 去除尾部斜杠（可选）
            
        参数:
            url: 原始URL
            
        返回:
            标准化后的URL，失败返回空字符串
        """
        try:
            parsed = urlparse(url)
            
            # 只接受http和https协议
            if parsed.scheme not in ('http', 'https'):
                return ""
            
            # 去除默认端口
            netloc = parsed.netloc.lower()
            if ':' in netloc:
                host, port = netloc.split(':', 1)
                if (parsed.scheme == 'http' and port == '80') or \
                   (parsed.scheme == 'https' and port == '443'):
                    netloc = host
            
            # 重构URL（去除fragment）
            normalized = urlunparse((
                parsed.scheme.lower(),  # 协议小写
                netloc,                 # 域名小写（已去除默认端口）
                parsed.path,
                parsed.params,
                parsed.query,
                ''  # 去除fragment
            ))
            
            return normalized
        
        except Exception:
            return ""
    
    def extract_links_with_text(self, html: str, base_url: str) -> List[Dict[str, str]]:
        """
        提取链接及其锚文本（扩展方法，非接口要求）
        
        参数:
            html: HTML内容
            base_url: 页面基础URL
            
        返回:
            列表，每项包含 {'url': '...', 'text': '...'}
        """
        if not html or not base_url:
            return []
        
        try:
            soup = BeautifulSoup(html, self._parser)
            links_with_text = []
            
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()
                
                if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    continue
                
                absolute_url = urljoin(base_url, href)
                normalized_url = self._normalize_url(absolute_url)
                
                if normalized_url:
                    # 提取链接文本
                    link_text = a_tag.get_text(strip=True)
                    links_with_text.append({
                        'url': normalized_url,
                        'text': link_text or ''
                    })
            
            return links_with_text
        
        except Exception as e:
            print(f"链接和文本提取失败: {str(e)}")
            return []
