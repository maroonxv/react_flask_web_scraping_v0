"""
scraping_app_v0\backend\src\shared\event_handlers\websocket_handler.py
将日志发送至前端浏览器
"""


from flask_socketio import SocketIO
from typing import Optional
from .base_handler import BaseEventHandler
import logging

class WebSocketEventHandler(BaseEventHandler):
    """
    WebSocket事件处理器
    职责：
    1. 接收领域事件并转换为前端友好格式
    2. 通过WebSocket实时推送到前端
    3. 支持按任务房间分组推送（只推送给订阅该任务的客户端）
    """
    
    def __init__(self, socketio: SocketIO, namespace: str = '/crawl'):
        """
        初始化WebSocket处理器
        
        参数:
            socketio: Flask-SocketIO实例
            namespace: WebSocket命名空间，默认 '/crawl'
        """
        self._socketio = socketio
        self._namespace = namespace
        self._logger = logging.getLogger(__name__)
    
    def handle(self, event) -> None:
        """
        处理事件：通过WebSocket推送到前端
        
        参数:
            event: DomainEvent 实例
        """
        task_id = event.task_id
        
        # 转换事件为前端格式（使用基类方法）
        log_entry = self._format_event_to_log(event)
        
        # 添加额外的前端需要的字段
        frontend_message = {
            **log_entry,
            "task_id": task_id,
            "event_type": event.event_type,
            # 添加进度信息（如果有）
            "progress": self._extract_progress_info(event)
        }
        
        try:
            # 推送到指定任务的房间（只有加入该房间的客户端会收到）
            self._socketio.emit(
                'crawl_log',               # 事件名称
                frontend_message,          # 数据
                namespace=self._namespace, # 命名空间
                room=task_id               # 房间（任务ID）
            )
            
            self._logger.debug(f"WebSocket推送成功: {event.event_type} -> 任务 {task_id}")
        
        except Exception as e:
            self._logger.error(f"WebSocket推送失败: {str(e)}")
    
    def _extract_progress_info(self, event) -> Optional[dict]:
        """
        从事件中提取进度信息（可选）
        
        参数:
            event: DomainEvent实例
            
        返回:
            进度信息字典或None
        """
        event_type = event.event_type
        data = event.data
        
        # 根据事件类型提取进度信息
        if event_type == "PAGE_CRAWLED":
            return {
                "current_depth": data.get('depth', 0),
                "pages_crawled": data.get('pages_crawled', 0),  # 如果事件包含累计数
                "pdfs_found": data.get('pdfs_found', 0)
            }
        
        elif event_type == "CRAWL_COMPLETED":
            return {
                "total_pages": data.get('total_pages', 0),
                "total_pdfs": data.get('total_pdfs', 0),
                "elapsed_time": data.get('elapsed_time', 0),
                "status": "completed"
            }
        
        elif event_type == "CRAWL_ERROR":
            return {
                "error_count": data.get('error_count', 1),
                "status": "error"
            }
        
        return None
    
    def broadcast_to_all(self, message: dict) -> None:
        """
        广播消息到所有连接的客户端（不分房间）
        
        参数:
            message: 消息字典
        """
        try:
            self._socketio.emit(
                'broadcast',
                message,
                namespace=self._namespace
            )
        except Exception as e:
            self._logger.error(f"广播失败: {str(e)}")
    
    def send_to_task(self, task_id: str, message: dict) -> None:
        """
        发送消息到指定任务的房间
        
        参数:
            task_id: 任务ID
            message: 消息字典
        """
        try:
            self._socketio.emit(
                'task_message',
                message,
                namespace=self._namespace,
                room=task_id
            )
        except Exception as e:
            self._logger.error(f"发送消息到任务 {task_id} 失败: {str(e)}")
