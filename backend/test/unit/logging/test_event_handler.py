import pytest
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

# Ensure backend directory is in python path
backend_dir = Path(__file__).resolve().parents[3]
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from src.shared.handlers.logging_handler import DailyRotatingFileHandler

class TestDailyRotatingFileHandler:
    
    @pytest.fixture
    def log_dir(self, tmp_path):
        """Fixture: 提供一个临时的日志目录"""
        return tmp_path / "logs" / "error"

    @pytest.fixture
    def handler(self, log_dir):
        """Fixture: 提供一个 DailyRotatingFileHandler 实例"""
        # 确保目录不存在，以测试自动创建功能
        # 注意：tmp_path 是存在的，但 log_dir (tmp_path/logs/error) 尚未创建
        suffix = "error.log"
        handler = DailyRotatingFileHandler(str(log_dir), suffix, backup_count=5)
        yield handler
        handler.close()

    def test_initialization_creates_directory(self, log_dir):
        """测试初始化时是否自动创建日志目录"""
        assert not log_dir.exists()
        
        # 初始化 handler
        handler = DailyRotatingFileHandler(str(log_dir), "test.log")
        handler.close()
        
        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_initial_filename_format(self, log_dir):
        """测试初始文件名是否符合 {Date}_{Suffix} 格式"""
        suffix = "test_app.log"
        
        # Mock datetime to a fixed date
        fixed_date = datetime(2025, 1, 1)
        with patch('src.shared.handlers.logging_handler.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_date
            # datetime.now() is called in __init__
            
            handler = DailyRotatingFileHandler(str(log_dir), suffix)
            
            expected_name = log_dir / "2025-01-01_test_app.log"
            
            # 检查 handler 的 baseFilename 属性
            # TimedRotatingFileHandler 将路径存储在 baseFilename 中
            assert Path(handler.baseFilename).resolve() == expected_name.resolve()
            
            handler.close()

    def test_custom_namer_logic(self, handler):
        """测试自定义轮转命名逻辑"""
        # 假设轮转机制生成了默认名称： /path/to/2025-11-30_error.log.2025-11-29
        # 我们希望它变成： /path/to/2025-11-29_error.log
        
        log_dir = Path(handler.baseFilename).parent
        base_name = f"2025-11-30_{handler.file_name_suffix}" # 当前文件名
        rotated_suffix = "2025-11-29" # 轮转附加的日期
        
        default_rotated_name = str(log_dir / f"{base_name}.{rotated_suffix}")
        
        # 调用 namer
        new_name = handler.namer(default_rotated_name)
        
        expected_name = str(log_dir / f"2025-11-29_{handler.file_name_suffix}")
        assert new_name == expected_name

    def test_custom_namer_edge_cases(self, handler):
        """测试 namer 的边界情况"""
        # Case 1: 无法解析日期后缀（例如没有点号）
        bad_name = str(Path(handler.baseFilename).parent / "invalid_name_format")
        assert handler.namer(bad_name) == bad_name
        
        # Case 2: 后缀不是标准日期格式 (长度不对或没有横杠)
        bad_suffix_name = str(Path(handler.baseFilename).parent / "base.log.123")
        assert handler.namer(bad_suffix_name) == bad_suffix_name

    def test_encoding_is_utf8(self, handler):
        """测试文件编码是否强制为 UTF-8"""
        assert handler.encoding == 'utf-8'

    def test_backup_count_setting(self, handler):
        """测试 backupCount 设置"""
        assert handler.backupCount == 5

    def test_actual_logging(self, handler):
        """集成测试：测试实际写入日志"""
        logger = logging.getLogger("test_daily_rotating")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        
        msg = "这是一条测试日志 - 中文"
        logger.info(msg)
        
        # 读取文件验证内容
        log_file = Path(handler.baseFilename)
        assert log_file.exists()
        
        content = log_file.read_text(encoding='utf-8')
        assert msg in content
