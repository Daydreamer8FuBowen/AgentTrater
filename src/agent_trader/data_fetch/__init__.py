"""数据抓取模块入口。导出核心类和便捷函数。"""

from .models import CleanedNewsItem, NewsIngestionResult
from .news_fetcher import NewsFetcher

__all__ = ["CleanedNewsItem", "NewsFetcher", "NewsIngestionResult"]
