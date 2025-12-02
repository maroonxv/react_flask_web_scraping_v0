import sys
import os
sys.path.append(os.getcwd())

try:
    from src.crawl.infrastructure.crawl_domain_service_impl import CrawlDomainServiceImpl
    from src.crawl.infrastructure.html_parser_impl import HtmlParserImpl
    from src.crawl.infrastructure.http_client_impl import HttpClientImpl
    from src.crawl.infrastructure.robots_txt_parser_impl import RobotsTxtParserImpl
    from src.crawl.services.crawler_service import CrawlerService
    print("Imports successful")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
