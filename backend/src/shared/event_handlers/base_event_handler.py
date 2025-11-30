
from abc import ABC, abstractmethod
from datetime import datetime
from src.shared.domain.events import DomainEvent

class BaseEventHandler(ABC):
    """
    事件处理器基类
    提供通用的事件格式化方法
    """
    
    @abstractmethod
    def handle(self, event: DomainEvent) -> None:
        """
        处理事件（子类必须实现）
        
        参数:
            event: DomainEvent 实例
        """
        pass
    
    def _format_event_to_log(self, event: DomainEvent) -> dict:
        """
        将领域事件转换为日志格式（通用方法）
        
        参数:
            event: DomainEvent实例
            
        返回:
            格式化的日志字典
        """
        # 根据事件类型生成人类可读的消息
        message, level = self._get_message_and_level(event)
        
        return {
            "timestamp": self._format_timestamp(event.timestamp),
            "level": level,
            "message": message,
            "event_type": event.event_type,
            "task_id": event.task_id,
            "data": event.data
        }
    
    def _get_message_and_level(self, event: DomainEvent) -> tuple[str, str]:
        """
        根据事件类型生成消息和日志级别
        
        返回:
            (message, level) 元组
        """
        event_type = event.event_type
        data = event.data
        
        # --- 任务生命周期事件 (Task Life Cycle) ---
        if event_type == "TaskCreatedEvent":
            return (
                f"▶ 任务创建: {data.get('start_url', 'N/A')} "
                f"[策略: {data.get('strategy', 'BFS')}, 最大深度: {data.get('max_depth', 3)}]",
                "INFO"
            )
        
        elif event_type == "TaskStartedEvent" or event_type == "CRAWL_STARTED":
             return (
                f"▶ 任务开始", 
                "INFO"
            )
        
        elif event_type == "TaskPausedEvent" or event_type == "CRAWL_PAUSED":
            return (
                f"⏸ 任务已暂停",
                "WARNING"
            )
            
        elif event_type == "TaskResumedEvent" or event_type == "CRAWL_RESUMED":
            return (
                f"▶ 任务已恢复",
                "INFO"
            )
            
        elif event_type == "TaskCompletedEvent" or event_type == "CRAWL_COMPLETED":
            total_pages = data.get('total_pages', 0)
            total_pdfs = data.get('total_pdfs', 0)
            elapsed_time = data.get('elapsed_time', 0)
            return (
                f"✓ 爬取完成! 共爬取 {total_pages} 个页面, "
                f"发现 {total_pdfs} 个PDF "
                f"(耗时: {elapsed_time:.1f}秒)",
                "SUCCESS"
            )
        
        elif event_type == "TaskFailedEvent" or event_type == "CRAWL_STOPPED":
             # 注意：CRAWL_STOPPED 在旧逻辑中是 Warning，TaskFailed 是 Error
             if event_type == "TaskFailedEvent":
                 return (f"✗ 任务失败: {data.get('error_message', '未知错误')}", "ERROR")
             return (f"⏹ 任务已停止", "WARNING")

        # --- 爬取过程事件 (Crawl Process) ---
        
        elif event_type == "PageCrawledEvent" or event_type == "PAGE_CRAWLED":
            title = data.get('title', '无标题')
            url = data.get('url', '')
            depth = data.get('depth', 0)
            pdf_count = data.get('pdf_count', 0)
            
            pdf_info = f", 发现{pdf_count}个PDF" if pdf_count > 0 else ""
            return (
                f"✓ 爬取成功: {title} (深度: {depth}{pdf_info})\n  URL: {url}",
                "INFO"
            )
        
        elif event_type == "PdfFoundEvent" or event_type == "PDF_FOUND":
            pdf_urls = data.get('pdf_urls', [])
            source_page = data.get('source_page_url', data.get('source_page', ''))
            count = data.get('count', 0)
            
            # 只显示前3个PDF的文件名
            pdf_names = [url.split('/')[-1] for url in pdf_urls[:3]]
            more = f" (+{count - 3}个更多)" if count > 3 else ""
            
            return (
                f"📄 发现 {count} 个PDF: {', '.join(pdf_names)}{more}\n"
                f"  来源: {source_page}",
                "SUCCESS"
            )
        
        elif event_type == "CrawlErrorEvent" or event_type == "CRAWL_ERROR":
            url = data.get('url', '')
            error_type = data.get('error_type', 'UNKNOWN')
            error_message = data.get('error_message', '')
            
            return (
                f"✗ 爬取失败 [{error_type}]: {url}\n"
                f"  错误: {error_message}",
                "ERROR"
            )
        
        elif event_type == "LinkFilteredEvent":
            return (
                f"∅ 链接过滤: {data.get('url')} ({data.get('reason')})",
                "DEBUG"
            )
            
        else:
            # 未知事件类型
            return (
                f"事件: {event_type}",
                "DEBUG"
            )
    
    def _format_timestamp(self, timestamp: datetime) -> str:
        """格式化时间戳"""
        if not isinstance(timestamp, datetime):
             return str(timestamp)
        return timestamp.strftime('%Y-%m-%d %H:%M:%S')
