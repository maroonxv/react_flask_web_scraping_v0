import logging.handlers
from pathlib import Path
from datetime import datetime
import os

class DailyRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    自定义按天轮转的文件处理器
    
    特点：
    1. 自动创建日志目录
    2. 强制使用 UTF-8 编码
    3. 使用 {Date}_{Name}.log 的命名格式（支持轮转）
    """
    
    def __init__(self, log_dir: str, file_name_suffix: str, backup_count: int = 30):
        """
        初始化
        
        参数:
            log_dir: 日志存放目录 (e.g. "backend/logs/error")
            file_name_suffix: 日志文件名后缀 (e.g. "error.log")
            backup_count: 保留天数
        """
        # 确保目录存在
        self.log_dir_path = Path(log_dir)
        self.log_dir_path.mkdir(parents=True, exist_ok=True)
        
        # 构造初始文件名: {Today}_{Suffix}
        today = datetime.now().strftime('%Y-%m-%d')
        filename = self.log_dir_path / f"{today}_{file_name_suffix}"
        
        super().__init__(
            filename=str(filename),
            when='MIDNIGHT',
            interval=1,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # 设置自定义 namer，用于轮转后的文件命名
        self.namer = self._custom_namer
        self.file_name_suffix = file_name_suffix

    def _custom_namer(self, default_name: str) -> str:
        """
        自定义轮转后的文件名
        
        默认 default_name 格式: .../2025-11-30_error.log.2025-11-29
        目标格式: .../2025-11-29_error.log
        """
        # default_name 是轮转逻辑生成的临时名称，通常是 base_filename + "." + date_suffix
        # 例如: .../2025-11-30_error.log.2025-11-29
        
        path_obj = Path(default_name)
        dir_name = path_obj.parent
        name = path_obj.name
        
        # 尝试提取日期后缀 (TimedRotatingFileHandler 默认附加 .YYYY-MM-DD)
        if '.' in name:
            parts = name.split('.')
            # 假设最后一部分是日期 (YYYY-MM-DD)
            date_part = parts[-1]
            
            # 简单验证日期格式 (可选)
            if len(date_part) == 10 and '-' in date_part:
                # 构造新名称: {Date}_{Suffix}
                new_name = f"{date_part}_{self.file_name_suffix}"
                return str(dir_name / new_name)
        
        return default_name
