# shared/event_handlers/logging_handler.py
from ..logging_config import get_task_lifecycle_logger, get_crawl_process_logger

class LoggingEventHandler(BaseEventHandler):
    def __init__(self):
        self._lifecycle_logger = get_task_lifecycle_logger()
        self._process_logger = get_crawl_process_logger()
    
    def handle(self, event):
        if event.event_type in ['TaskStarted', 'TaskCompleted']:
            self._lifecycle_logger.info(
                event.event_type,
                extra=event.to_dict()
            )
        elif event.event_type in ['PageCrawled', 'PDFsDiscovered']:
            self._process_logger.info(
                event.event_type,
                extra=event.to_dict()
            )
