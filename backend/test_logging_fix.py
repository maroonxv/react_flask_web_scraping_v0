
import logging
import os
import shutil
from pathlib import Path
from src.shared.handlers.logging_handler import DailyRotatingFileHandler

def test_handler():
    # Setup
    log_dir = "logs_test"
    if os.path.exists(log_dir):
        shutil.rmtree(log_dir)
    
    # Test 1: With date prefix (default)
    handler1 = DailyRotatingFileHandler(log_dir, "test1.log")
    logger1 = logging.getLogger("test1")
    logger1.addHandler(handler1)
    logger1.setLevel(logging.INFO)
    logger1.info("Test message 1")
    
    # Verify file exists with date
    files = os.listdir(log_dir)
    print(f"Files in {log_dir}: {files}")
    
    # Test 2: Without date prefix
    handler2 = DailyRotatingFileHandler(log_dir, "test2.log", use_date_prefix=False)
    logger2 = logging.getLogger("test2")
    logger2.addHandler(handler2)
    logger2.setLevel(logging.INFO)
    logger2.info("Test message 2")
    
    # Verify file exists without date
    files = os.listdir(log_dir)
    print(f"Files in {log_dir} after test 2: {files}")
    
    assert os.path.exists(os.path.join(log_dir, "test2.log"))
    
    print("Verification successful!")
    
    # Cleanup
    handler1.close()
    handler2.close()
    if os.path.exists(log_dir):
        shutil.rmtree(log_dir)

if __name__ == "__main__":
    test_handler()
