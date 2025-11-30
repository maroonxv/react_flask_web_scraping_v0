# shared/handlers/websocket_handler.py
"""
自定义 WebSocket Logging Handler
职责：拦截技术日志并推送到前端浏览器
"""

import logging
from flask_socketio import SocketIO
from typing import Optional
from datetime import datetime


class WebSocketLoggingHandler(logging.Handler):
    """
    自定义日志处理器：将技术日志通过WebSocket推送到前端
    
    用法：
        handler = WebSocketLoggingHandler(socketio, namespace='/crawl')
        logger.addHandler(handler)
    """
    
    def __init__(self, socketio: SocketIO, namespace: str = '/crawl'):
        """
        初始化WebSocket日志处理器
        
        参数:
            socketio: Flask-SocketIO实例
            namespace: WebSocket命名空间
        """
        super().__init__()
        self._socketio = socketio
        self._namespace = namespace
        self._internal_logger = logging.getLogger('internal.websocket_logging_handler')
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        处理日志记录：推送到前端
        
        参数:
            record: logging.LogRecord 实例
        """
        try:
            # 格式化日志记录
            log_message = self._format_log_record(record)
            
            # 通过WebSocket广播到所有连接的客户端
            self._socketio.emit(
                'tech_log',              # 技术日志事件名（区别于业务日志的 'crawl_log'）
                log_message,
                namespace=self._namespace,
                broadcast=True           # 广播给所有客户端
            )
            
        except Exception as e:
            # 避免日志处理器本身的错误影响应用
            # 注意：这里使用 print 或者写入文件，因为 internal_logger 可能也会触发 emit 导致递归
            # 但通常 internal logger 配置为只写文件
            try:
                self._internal_logger.error(f"WebSocket日志推送失败: {str(e)}")
            except:
                print(f"WebSocket日志推送严重失败: {str(e)}")
    
    def _format_log_record(self, record: logging.LogRecord) -> dict:
        """
        将 LogRecord 转换为前端友好的格式
        
        参数:
            record: logging.LogRecord 实例
            
        返回:
            前端可用的日志字典
        """
        # 提取日志类型（从logger名称）
        # 例如：'infrastructure.error' → 'error'
        #       'infrastructure.perf' → 'performance'
        logger_parts = record.name.split('.')
        raw_category = logger_parts[-1] if len(logger_parts) > 1 else 'unknown'
        
        # 映射分类名称
        category_map = {
            'perf': 'performance',
            'error': 'error'
        }
        log_category = category_map.get(raw_category, raw_category)
        
        # 构建前端消息
        log_message = {
            # 基础信息
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'category': log_category,  # error, performance
            'logger': record.name,
            'message': record.getMessage(),
            
            # 位置信息
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            
            # 扩展信息（从 extra 参数）
            'extra': self._extract_extra_data(record),
            
            # 异常信息（如果有）
            'exception': self._format_exception(record) if record.exc_info else None
        }
        
        return log_message
    
    def _extract_extra_data(self, record: logging.LogRecord) -> dict:
        """
        提取 logger.error(..., extra={...}) 中的 extra 数据
        """
        # 标准 LogRecord 属性
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'message', 'pathname', 'process', 'processName', 'relativeCreated',
            'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
            'taskName' # Python 3.12+
        }
        
        # 提取自定义属性
        extra = {}
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                try:
                    # 尝试序列化或只保留基本类型，防止循环引用或无法JSON序列化的对象
                    extra[key] = value
                except:
                    extra[key] = str(value)
        
        return extra
    
    def _format_exception(self, record: logging.LogRecord) -> Optional[str]:
        """格式化异常信息"""
        if record.exc_info:
            # 如果配置了formatter，使用formatter格式化异常
            if self.formatter:
                return self.formatter.formatException(record.exc_info)
            # 否则使用默认格式
            return logging.Formatter().formatException(record.exc_info)
        return None
