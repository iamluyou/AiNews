from .base import BaseCrawler
from .kr36 import Kr36Crawler
from .aiera import AieraCrawler
from .radar import RadarCrawler
from .qbit import QbitCrawler

# 爬虫注册表
CRAWLER_REGISTRY = {
    "kr36": Kr36Crawler,
    "aiera": AieraCrawler,
    "radar": RadarCrawler,
    "qbit": QbitCrawler,
}

__all__ = [
    "BaseCrawler",
    "CRAWLER_REGISTRY",
    "Kr36Crawler",
    "AieraCrawler",
    "RadarCrawler",
    "QbitCrawler",
]
