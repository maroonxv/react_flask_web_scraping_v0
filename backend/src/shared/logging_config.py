# scraping_app_v0\backend\src\shared\logging_config.py
"""
日志配置模块
统一管理4类日志：
1. task_lifecycle/ - 任务生命周期日志（事件驱动）
2. crawl_process/ - 爬取过程日志（事件驱动）
3. error/ - 错误日志（Infrastructure层直接调用）
4. performance/ - 性能监控日志（Infrastructure层直接调用）

文件命名格式：{日期}_{日志类型}.log
例如：2025-11-30_task_lifecycle.log
"""

import logging.config
from pathlib import Path
from datetime import datetime
from typing import Optional
from flask_socketio import SocketIO
from src.shared.handlers.websocket_handler import WebSocketLoggingHandler
from src.shared.handlers.logging_handler import DailyRotatingFileHandler


def setup_logging(socketio: Optional[SocketIO] = None):
    """
    初始化并配置所有logger
    应在应用启动时调用：setup_logging()
    """
    
    # 获取日志根目录（backend/logs/）
    backend_dir = Path(__file__).resolve().parent.parent.parent
    log_root_dir = backend_dir / 'logs'
    
    # 创建各类日志的子目录路径 (用于配置 DailyRotatingFileHandler)
    task_lifecycle_dir = log_root_dir / 'task_lifecycle'
    crawl_process_dir = log_root_dir / 'crawl_process'
    error_dir = log_root_dir / 'error'
    performance_dir = log_root_dir / 'performance'
    
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        
        # ==================== 格式化器 ====================
        'formatters': {
            'json': {
                '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
                'timestamp': True
            },
            'simple': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        
        # ==================== 处理器 ====================
        'handlers': {
            # ---------- 业务日志处理器 ----------
            
            'task_lifecycle_file': {
                '()': DailyRotatingFileHandler,  # 使用自定义处理器
                'log_dir': str(task_lifecycle_dir),
                'file_name_suffix': 'task_lifecycle.log',
                'backup_count': 30,
                'formatter': 'json'
            },
            
            'crawl_process_file': {
                '()': DailyRotatingFileHandler,
                'log_dir': str(crawl_process_dir),
                'file_name_suffix': 'crawl_process.log',
                'backup_count': 30,
                'formatter': 'json'
            },
            
            # ---------- 技术日志处理器 ----------
            
            'error_file': {
                '()': DailyRotatingFileHandler,
                'log_dir': str(error_dir),
                'file_name_suffix': 'error.log',
                'backup_count': 30,
                'formatter': 'json'
            },
            
            'performance_file': {
                '()': DailyRotatingFileHandler,
                'log_dir': str(performance_dir),
                'file_name_suffix': 'performance.log',
                'backup_count': 7,
                'formatter': 'json'
            },
            
            # ---------- 控制台输出 ----------
            
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
                'level': 'INFO'
            }
        },
        
        # ==================== Logger配置 ====================
        'loggers': {
            # ---------- 业务日志Logger（由EventHandler使用） ----------
            
            'domain.task_lifecycle': {
                'handlers': ['task_lifecycle_file', 'console'],
                'level': 'INFO',
                'propagate': False
            },
            
            'domain.crawl_process': {
                'handlers': ['crawl_process_file', 'console'],
                'level': 'INFO',
                'propagate': False
            },
            
            # ---------- 技术日志Logger（Infrastructure层直接使用） ----------
            
            'infrastructure.error': {
                'handlers': ['error_file', 'console'],
                'level': 'ERROR',
                'propagate': False
            },
            
            'infrastructure.perf': {
                'handlers': ['performance_file'],
                'level': 'INFO',
                'propagate': False
            }
        },
        
        # ==================== 根Logger（兜底） ====================
        'root': {
            'level': 'INFO',
            'handlers': ['console']
        }
    }
    
    # 应用配置
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # ✅ 如果提供了 socketio，添加 WebSocket handler 到技术日志
    if socketio:
        _add_websocket_handlers(socketio)
    
    # 记录启动日志
    logger = logging.getLogger('domain.task_lifecycle')
    logger.info("日志系统初始化完成", extra={
        'log_root_dir': str(log_root_dir),
        'config_type': 'DailyRotatingFileHandler'
    })


def _add_websocket_handlers(socketio: SocketIO):
    """
    动态添加 WebSocket 处理器到技术日志 Logger
    """
    # 1. 创建技术日志处理器 (使用默认 event_name='tech_log')
    tech_ws_handler = WebSocketLoggingHandler(socketio)
    tech_ws_handler.setFormatter(logging.Formatter('%(message)s'))
    
    # 2. 创建业务日志处理器 (使用 event_name='crawl_log')
    business_ws_handler = WebSocketLoggingHandler(socketio, event_name='crawl_log')
    business_ws_handler.setFormatter(logging.Formatter('%(message)s'))
    
    # 获取目标 logger
    error_logger = logging.getLogger('infrastructure.error')
    perf_logger = logging.getLogger('infrastructure.perf')
    lifecycle_logger = logging.getLogger('domain.task_lifecycle')
    process_logger = logging.getLogger('domain.crawl_process')
    
    # 添加处理器 (技术日志)
    if not any(isinstance(h, WebSocketLoggingHandler) and h._event_name == 'tech_log' for h in error_logger.handlers):
        error_logger.addHandler(tech_ws_handler)
        
    if not any(isinstance(h, WebSocketLoggingHandler) and h._event_name == 'tech_log' for h in perf_logger.handlers):
        perf_logger.addHandler(tech_ws_handler)

    # 添加处理器 (业务日志)
    if not any(isinstance(h, WebSocketLoggingHandler) and h._event_name == 'crawl_log' for h in lifecycle_logger.handlers):
        lifecycle_logger.addHandler(business_ws_handler)

    if not any(isinstance(h, WebSocketLoggingHandler) and h._event_name == 'crawl_log' for h in process_logger.handlers):
        process_logger.addHandler(business_ws_handler)
    
    # 记录调试信息
    logging.getLogger('root').info("WebSocket日志处理器已附加到 all 通道 (tech_log & crawl_log)")
