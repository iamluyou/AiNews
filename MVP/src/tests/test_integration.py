"""
集成测试
"""
import pytest
from pathlib import Path
from datetime import datetime

from news_agent.config import Config, SchedulerConfig, CrawlersConfig
from news_agent.models.news import NewsItem
from news_agent.storage.database import init_db, session_scope, NewsModel
from news_agent.storage.repository import NewsRepository


@pytest.fixture
def temp_db(tmp_path):
    """临时数据库 fixture"""
    db_path = tmp_path / "test.db"
    init_db(str(db_path))
    return str(db_path)


class TestConfig:
    """测试配置"""

    def test_config_defaults(self):
        """测试默认配置"""
        config = Config()
        assert config.scheduler is not None
        assert len(config.scheduler.cron_times) == 3
        assert config.crawlers is not None
        assert len(config.crawlers.enabled) == 4


class TestStorage:
    """测试存储模块"""

    def test_add_and_get_news(self, temp_db):
        """测试添加和获取新闻"""
        news = NewsItem(
            title="测试新闻",
            url="https://example.com/test",
            source="测试来源",
            publish_time=datetime(2024, 1, 1, 12, 0),
            content="测试内容",
        )

        # 添加新闻
        result = NewsRepository.add(news)
        assert result is True

        # 获取新闻
        retrieved = NewsRepository.get_by_url("https://example.com/test")
        assert retrieved is not None
        assert retrieved.title == "测试新闻"
        assert retrieved.source == "测试来源"

    def test_add_batch(self, temp_db):
        """测试批量添加"""
        news_list = []
        for i in range(5):
            news = NewsItem(
                title=f"新闻{i}",
                url=f"https://example.com/{i}",
                source="测试来源",
            )
            news_list.append(news)

        count = NewsRepository.add_batch(news_list)
        assert count == 5

        latest = NewsRepository.get_latest(limit=10)
        assert len(latest) == 5

    def test_exists(self, temp_db):
        """测试新闻存在检查"""
        news = NewsItem(
            title="测试新闻",
            url="https://example.com/test",
            source="测试来源",
        )

        assert NewsRepository.exists("https://example.com/test") is False
        NewsRepository.add(news)
        assert NewsRepository.exists("https://example.com/test") is True


class TestNewsItem:
    """测试新闻数据模型"""

    def test_news_item_creation(self):
        """测试新闻项创建"""
        news = NewsItem(
            title="测试新闻",
            url="https://example.com/test",
            source="测试来源",
        )
        assert news.title == "测试新闻"
        assert news.url == "https://example.com/test"
        assert news.source == "测试来源"

    def test_news_item_to_dict(self):
        """测试新闻项转字典"""
        news = NewsItem(
            title="测试新闻",
            url="https://example.com/test",
            source="测试来源",
            ai_relevance_score=0.8,
        )
        data = news.to_dict()
        assert data["title"] == "测试新闻"
        assert data["ai_relevance_score"] == 0.8

    def test_news_item_from_dict(self):
        """测试从字典创建新闻项"""
        data = {
            "title": "测试新闻",
            "url": "https://example.com/test",
            "source": "测试来源",
        }
        news = NewsItem.from_dict(data)
        assert news.title == "测试新闻"
        assert news.url == "https://example.com/test"
