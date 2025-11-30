import sys
import os

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, 'backend')
sys.path.append(backend_dir)

try:
    from src.crawl.services.crawler_service import CrawlerService
    print("CrawlerService imported successfully")
    from src.crawl.domain.entity.crawl_task import CrawlTask
    print("CrawlTask imported successfully")
    from src.crawl.view.crawler_view import _service, inject_event_bus
    print("crawler_view imported successfully")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
