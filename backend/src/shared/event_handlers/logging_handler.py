# shared/event_handlers/logging_handler.py
from typing import Dict, List, Optional, Union
from collections import deque
from pathlib import Path
import logging
import logging.handlers
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pythonjsonlogger import jsonlogger
from .base_event_handler import BaseEventHandler
from src.shared.domain.events import DomainEvent

class LoggingEventHandler(BaseEventHandler):
    """
    日志事件处理器
    职责：
    1. 捕获领域事件并转换为日志格式
    2. 按任务ID分组存储日志到内存队列
    3. 提供日志查询接口供API调用
    """
    
    def __init__(self, max_logs_per_task: int = 1000):
        """
        初始化日志处理器
        
        参数:
            max_logs_per_task: 每个任务最多保留的日志条数（超出则丢弃最旧的）
        """
        # 每个任务的日志队列: {task_id: deque}
        self._task_logs: Dict[str, deque] = {}
        self._max_logs_per_task = max_logs_per_task

        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.INFO)

        # 确保日志目录存在
        self.backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        self.log_dir = self.backend_dir / 'logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.log_handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(self.log_dir / 'crawler_log.log'),  # 基础文件名
            when='MIDNIGHT',         # 每天午夜切换
            interval=1,              # 间隔1天
            backupCount=30,          # 保留30天的日志
            encoding='utf-8'
        )

        # 自定义备份文件的命名规则
        self.log_handler.namer = self._custom_namer

        self.log_handler.setFormatter(
            jsonlogger.JsonFormatter(
                '%(asctime)s %(name)s %(levelname)s %(message)s',
                timestamp=True
            )
        )
        # 避免重复添加handler
        if not self._logger.handlers:
            self._logger.addHandler(self.log_handler)


    def _custom_namer(self, default_name):
        """
        自定义日志文件命名
        默认名称格式：crawler_log.log.2025-11-30
        转换为：2025-11-30_crawler_log.log
        """
        # 提取日期部分（默认格式的最后部分）
        dir_name, base_name = Path(default_name).parent, Path(default_name).name
        
        # 提取日期后缀（如 .2025-11-30）
        if '.' in base_name:
            parts = base_name.split('.')
            if len(parts) >= 3:
                date_suffix = parts[-1]  # 获取日期部分
                # 重新组合为：日期_crawler_log.log
                new_name = f"{date_suffix}_crawler_log.log"
                return str(dir_name / new_name)
        
        return default_name
    
# -------------------- 最重要的方法：将事件转换为日志格式并存储 --------------------

    def handle(self, event: DomainEvent) -> None:
        """
        处理事件：转换为日志格式并存储
        
        参数:
            event: DomainEvent 实例 (可能是 dataclass 或普通对象)
        """
        try:
            task_id = getattr(event, 'task_id', 'unknown_task')
            
            # 确保任务有日志队列
            if task_id not in self._task_logs:
                self._task_logs[task_id] = deque(maxlen=self._max_logs_per_task)
            
            # 转换事件为日志格式
            log_entry = self._format_event_to_log(event)
            
            # 存储日志
            self._task_logs[task_id].append(log_entry)

            # 记录到文件
            self._logger.info(log_entry)
            
        except Exception as e:
            # 避免日志处理本身的错误导致程序崩溃，但要记录错误（使用 print 或其他 logger）
            print(f"LoggingEventHandler error: {e}")

# -------------------- 日志查询接口（五个） --------------------

    def get_logs(self, task_id: str, last_n: Optional[int] = None) -> List[dict]:
        """
        获取任务日志
        
        参数:
            task_id: 任务ID
            last_n: 获取最近N条，None表示全部
            
        返回:
            日志字典列表
        """
        logs = self._task_logs.get(task_id, deque())
        
        if last_n:
            return list(logs)[-last_n:]
        return list(logs)
    
    def get_all_task_ids(self) -> List[str]:
        """获取所有有日志的任务ID列表"""
        return list(self._task_logs.keys())
    
    def get_log_count(self, task_id: str) -> int:
        """
        获取任务日志条数
        
        参数:
            task_id: 任务ID
            
        返回:
            日志条数
        """
        return len(self._task_logs.get(task_id, deque()))
    
    def get_logs_by_level(self, task_id: str, level: str) -> List[dict]:
        """
        获取指定级别的日志
        
        参数:
            task_id: 任务ID
            level: 日志级别 (INFO/ERROR/SUCCESS/WARNING)
            
        返回:
            过滤后的日志列表
        """
        logs = self._task_logs.get(task_id, deque())
        return [log for log in logs if log['level'] == level]
    
    def get_error_logs(self, task_id: str) -> List[dict]:
        """
        快捷方法：获取所有错误日志
        
        参数:
            task_id: 任务ID
            
        返回:
            错误日志列表
        """
        return self.get_logs_by_level(task_id, 'ERROR')

# -------------------- 清空和检查错误 --------------------
    
    def clear_logs(self, task_id: str) -> None:
        """
        清空指定任务的日志
        
        参数:
            task_id: 任务ID
        """
        if task_id in self._task_logs:
            self._task_logs[task_id].clear()

    def has_errors(self, task_id: str) -> bool:
        """
        检查任务是否有错误日志
        
        参数:
            task_id: 任务ID
            
        返回:
            True表示有错误
        """
        return len(self.get_error_logs(task_id)) > 0
