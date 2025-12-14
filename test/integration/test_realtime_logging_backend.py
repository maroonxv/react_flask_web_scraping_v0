import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.shared.event_bus import EventBus
from src.shared.event_handlers.logging_handler import LoggingEventHandler
from src.crawl.view import crawler_view
from src.crawl.domain.domain_event.crawl_process_event import PageCrawledEvent


class FakeSocketIO:
    def __init__(self):
        self.messages = []

    def emit(self, event, data, namespace=None, room=None, broadcast=False):
        self.messages.append(
            {
                "event": event,
                "data": data,
                "namespace": namespace,
                "room": room,
                "broadcast": broadcast,
            }
        )


def test_page_crawled_event_broadcasts_crawl_log():
    event_bus = EventBus()
    logging_handler = LoggingEventHandler()
    event_bus.subscribe_to_all(logging_handler.handle)

    fake_socketio = FakeSocketIO()
    crawler_view._service._event_bus = None
    crawler_view.init_realtime_logging(fake_socketio, event_bus)

    task_id = "task-realtime"
    event = PageCrawledEvent(
        task_id=task_id,
        url="http://example.com",
        title="Example Domain",
        depth=1,
        status_code=200,
        pdf_count=0,
    )
    event_bus.publish(event)

    crawl_msgs = [m for m in fake_socketio.messages if m["event"] == "crawl_log"]
    assert crawl_msgs
    msg = crawl_msgs[0]
    payload = msg["data"]

    assert msg["namespace"] == "/crawl"
    assert msg["room"] == task_id
    assert payload["task_id"] == task_id
    assert payload["event_type"] == "PageCrawledEvent"
    assert payload["data"]["url"] == "http://example.com"
    assert payload["data"]["title"] == "Example Domain"

