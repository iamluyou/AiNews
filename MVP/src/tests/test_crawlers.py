"""
爬虫模块测试
"""
import pytest
from datetime import datetime

from news_agent.crawlers import BaseCrawler, CRAWLER_REGISTRY
from news_agent.models.news import NewsItem


class TestBaseCrawler:
    """测试爬虫基类"""

    def test_crawler_registry(self):
        """测试爬虫注册表"""
        assert "kr36" in CRAWLER_REGISTRY
        assert "aiera" in CRAWLER_REGISTRY
        assert "radar" in CRAWLER_REGISTRY
        assert "qbit" in CRAWLER_REGISTRY

    def test_create_news_item(self):
        """测试创建新闻项"""

        # 创建一个测试爬虫实例
        class TestCrawler(BaseCrawler):
            name = "test"
            base_url = "https://example.com"
            source_name = "测试来源"

            def fetch(self):
                return []

        crawler = TestCrawler()

        news = crawler._create_news_item(
            title="测试新闻",
            url="/test",
            cover_image="https://example.com/img.jpg",
            publish_time=datetime(2024, 1, 1, 12, 0),
            content="测试内容",
        )

        assert isinstance(news, NewsItem)
        assert news.title == "测试新闻"
        assert news.url == "https://example.com/test"
        assert news.source == "测试来源"


class TestCrawlers:
    """测试各爬虫实例化"""

    @pytest.mark.parametrize("crawler_name", ["kr36", "aiera", "radar", "qbit"])
    def test_crawler_instantiation(self, crawler_name):
        """测试爬虫可以正常实例化"""
        crawler_cls = CRAWLER_REGISTRY[crawler_name]
        crawler = crawler_cls()
        assert crawler is not None
        assert crawler.name == crawler_name
        assert crawler.source_name is not None
