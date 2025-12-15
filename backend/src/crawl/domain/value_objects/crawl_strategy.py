from enum import Enum

class CrawlStrategy(Enum):
    BFS = "BFS"
    DFS = "DFS"
    BIG_SITE_FIRST = "BIG_SITE_FIRST"
