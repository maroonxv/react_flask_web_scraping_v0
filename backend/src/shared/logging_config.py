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


def setup_logging(socketio: Optional[SocketIO] = None):
    """
    初始化并配置所有logger
    应在应用启动时调用：setup_logging()
    """
    
    # 获取日志根目录（backend/logs/）
    backend_dir = Path(__file__).resolve().parent.parent
    log_root_dir = backend_dir / 'logs'
    
    # 创建各类日志的子目录
    task_lifecycle_dir = log_root_dir / 'task_lifecycle'
    crawl_process_dir = log_root_dir / 'crawl_process'
    error_dir = log_root_dir / 'error'
    performance_dir = log_root_dir / 'performance'
    
    # 确保所有目录存在
    task_lifecycle_dir.mkdir(parents=True, exist_ok=True)
    crawl_process_dir.mkdir(parents=True, exist_ok=True)
    error_dir.mkdir(parents=True, exist_ok=True)
    performance_dir.mkdir(parents=True, exist_ok=True)
    
    # 当前日期（用于初始文件名）
    today = datetime.now().strftime('%Y-%m-%d')
    
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
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'filename': str(task_lifecycle_dir / f'{today}_task_lifecycle.log'),
                'when': 'MIDNIGHT',         # 每天午夜切换
                'interval': 1,              # 间隔1天
                'backupCount': 30,          # 保留30天历史日志
                'encoding': 'utf-8',
                'formatter': 'json'
            },
            
            'crawl_process_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'filename': str(crawl_process_dir / f'{today}_crawl_process.log'),
                'when': 'MIDNIGHT',
                'interval': 1,
                'backupCount': 30,
                'encoding': 'utf-8',
                'formatter': 'json'
            },
            
            # ---------- 技术日志处理器 ----------
            
            'error_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'filename': str(error_dir / f'{today}_error.log'),
                'when': 'MIDNIGHT',
                'interval': 1,
                'backupCount': 30,          # 错误日志保留30天
                'encoding': 'utf-8',
                'formatter': 'json'
            },
            
            'performance_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'filename': str(performance_dir / f'{today}_performance.log'),
                'when': 'MIDNIGHT',
                'interval': 1,
                'backupCount': 7,           # 性能日志保留7天
                'encoding': 'utf-8',
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
    
    # 自定义文件命名（实现日期前缀命名）
    _setup_custom_namer()

    # ✅ 如果提供了 socketio，添加 WebSocket handler 到技术日志
    if socketio:
        _add_websocket_handlers(socketio)
    
    # 记录启动日志
    logger = logging.getLogger('domain.task_lifecycle')
    logger.info("日志系统初始化完成", extra={
        'log_root_dir': str(log_root_dir),
        'directories': {
            'task_lifecycle': str(task_lifecycle_dir),
            'crawl_process': str(crawl_process_dir),
            'error': str(error_dir),
            'performance': str(performance_dir)
        }
    })


def _setup_custom_namer():
    """
    为所有TimedRotatingFileHandler设置自定义命名规则
    
    默认命名（TimedRotatingFileHandler）：
    - 2025-11-30_task_lifecycle.log           # 当天文件
    - 2025-11-30_task_lifecycle.log.2025-11-29  # 轮转后文件
    
    自定义命名（修正后）：
    - 2025-11-30_task_lifecycle.log           # 当天文件
    - 2025-11-29_task_lifecycle.log           # 昨天文件
    """
    
    def custom_namer(default_name: str) -> str:
        """
        将TimedRotatingFileHandler的默认命名转换为日期前缀格式
        
        default_name示例：
        /path/to/logs/task_lifecycle/2025-11-30_task_lifecycle.log.2025-11-29
        
        转换为：
        /path/to/logs/task_lifecycle/2025-11-29_task_lifecycle.log
        """
        path = Path(default_name)
        dir_name = path.parent
        base_name = path.name
        
        # 检查是否是轮转后的文件（包含日期后缀）
        if '.' in base_name:
            parts = base_name.split('.')
            
            # 格式：2025-11-30_task_lifecycle.log.2025-11-29
            if len(parts) == 3 and parts[1] == 'log':
                # 提取日志类型（task_lifecycle/crawl_process/error/performance）
                log_type = parts[0].split('_', 1)[1]  # 从 "2025-11-30_task_lifecycle" 提取 "task_lifecycle"
                date_suffix = parts[2]                 # 提取日期 "2025-11-29"
                
                # 重组为：2025-11-29_task_lifecycle.log
                new_name = f"{date_suffix}_{log_type}.log"
                return str(dir_name / new_name)
        
        return default_name
    
    # 应用到所有TimedRotatingFileHandler
    for logger_name in ['domain.task_lifecycle', 'domain.crawl_process', 
                        'infrastructure.error', 'infrastructure.perf']:
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            if isinstance(handler, logging.handlers.TimedRotatingFileHandler):
                handler.namer = custom_namer


# ==================== 便捷获取Logger的函数 ====================

def get_task_lifecycle_logger() -> logging.Logger:
    """获取任务生命周期日志Logger（EventHandler使用）"""
    return logging.getLogger('domain.task_lifecycle')


def get_crawl_process_logger() -> logging.Logger:
    """获取爬取过程日志Logger（EventHandler使用）"""
    return logging.getLogger('domain.crawl_process')


def get_error_logger() -> logging.Logger:
    """获取错误日志Logger（Infrastructure层使用）"""
    return logging.getLogger('infrastructure.error')


def get_performance_logger() -> logging.Logger:
    """获取性能监控日志Logger（Infrastructure层使用）"""
    return logging.getLogger('infrastructure.perf')


