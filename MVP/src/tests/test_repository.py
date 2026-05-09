"""
Repository 模块测试
"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from news_agent.storage.repository import NewsRepository
from news_agent.storage.database import init_db
from news_agent.models.news import NewsItem


@pytest.fixture
def temp_db():
    """临时数据库 fixture"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        yield db_path
    finally:
        Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_news():
    """示例新闻数据"""
    return [
        NewsItem(
            title="Test News 1",
            url="https://example.com/1",
            source="TestSource",
            created_at=datetime(2024, 1, 1, 10, 0),
        ),
        NewsItem(
            title="Test News 2",
            url="https://example.com/2",
            source="TestSource",
            created_at=datetime(2024, 1, 1, 11, 0),
        ),
        NewsItem(
            title="Test News 3",
            url="https://example.com/3",
            source="TestSource",
            created_at=datetime(2024, 1, 1, 12, 0),
        ),
    ]


class TestNewsRepository:
    """测试 NewsRepository"""

    def test_add_single_news(self, temp_db, sample_news):
        """测试添加单条新闻"""
        news = sample_news[0]
        result = NewsRepository.add(news)
        assert result is True

        # 验证可以获取
        retrieved = NewsRepository.get_by_url(news.url)
        assert retrieved is not None
        assert retrieved.title == news.title
        assert retrieved.url == news.url

    def test_add_duplicate_news(self, temp_db, sample_news):
        """测试添加重复新闻（更新）"""
        news = sample_news[0]
        NewsRepository.add(news)

        # 添加重复的，应该返回 False
        news_dup = NewsItem(
            title="Updated Title",
            url=news.url,
            source="TestSource",
            created_at=datetime(2024, 1, 2),
        )
        result = NewsRepository.add(news_dup)
        assert result is False

        # 验证标题已更新
        retrieved = NewsRepository.get_by_url(news.url)
        assert retrieved.title == "Updated Title"

    def test_add_batch(self, temp_db, sample_news):
        """测试批量添加新闻"""
        count = NewsRepository.add_batch(sample_news)
        assert count == 3

        # 验证都已添加
        for news in sample_news:
            retrieved = NewsRepository.get_by_url(news.url)
            assert retrieved is not None

    def test_add_batch_with_duplicates(self, temp_db, sample_news):
        """测试批量添加包含重复的新闻"""
        # 先添加第一条
        NewsRepository.add(sample_news[0])

        # 批量添加（包含重复）
        count = NewsRepository.add_batch(sample_news)
        assert count == 2  # 只有2条新增

    def test_mark_as_sent_single(self, temp_db, sample_news):
        """测试标记单条为已发送"""
        NewsRepository.add(sample_news[0])

        count = NewsRepository.mark_as_sent([sample_news[0].url])
        assert count == 1

        assert NewsRepository.is_sent(sample_news[0].url) is True

    def test_mark_as_sent_batch(self, temp_db, sample_news):
        """测试批量标记为已发送"""
        NewsRepository.add_batch(sample_news)

        urls = [news.url for news in sample_news]
        count = NewsRepository.mark_as_sent(urls)
        assert count == 3

        for url in urls:
            assert NewsRepository.is_sent(url) is True

    def test_mark_as_sent_nonexistent(self, temp_db):
        """测试标记不存在的 URL"""
        count = NewsRepository.mark_as_sent(["https://nonexistent.com"])
        assert count == 0

    def test_get_by_source(self, temp_db, sample_news):
        """测试按来源获取"""
        NewsRepository.add_batch(sample_news)

        # 添加另一个来源的新闻
        other_news = NewsItem(
            title="Other News",
            url="https://example.com/other",
            source="OtherSource",
            created_at=datetime(2024, 1, 1),
        )
        NewsRepository.add(other_news)

        results = NewsRepository.get_by_source("TestSource")
        assert len(results) == 3

    def test_get_latest(self, temp_db, sample_news):
        """测试获取最新新闻"""
        NewsRepository.add_batch(sample_news)

        results = NewsRepository.get_latest(limit=2)
        assert len(results) == 2

    def test_get_unsent(self, temp_db, sample_news):
        """测试获取未发送新闻"""
        NewsRepository.add_batch(sample_news)

        # 标记第一条为已发送
        NewsRepository.mark_as_sent([sample_news[0].url])

        unsent = NewsRepository.get_unsent()
        assert len(unsent) == 2
        assert sample_news[0].url not in [n.url for n in unsent]

    def test_get_by_time_range(self, temp_db):
        """测试按时间范围获取"""
        # 创建有 publish_time 的新闻
        news_with_time = [
            NewsItem(
                title="Test News 1",
                url="https://example.com/1",
                source="TestSource",
                publish_time=datetime(2024, 1, 1, 10, 0),
                created_at=datetime(2024, 1, 1, 10, 0),
            ),
            NewsItem(
                title="Test News 2",
                url="https://example.com/2",
                source="TestSource",
                publish_time=datetime(2024, 1, 1, 11, 0),
                created_at=datetime(2024, 1, 1, 11, 0),
            ),
        ]
        NewsRepository.add_batch(news_with_time)

        start = datetime(2024, 1, 1, 9, 0)
        end = datetime(2024, 1, 1, 11, 30)

        results = NewsRepository.get_by_time_range(start, end)
        assert len(results) >= 1

    def test_exists(self, temp_db, sample_news):
        """测试检查存在"""
        NewsRepository.add(sample_news[0])

        assert NewsRepository.exists(sample_news[0].url) is True
        assert NewsRepository.exists("https://nonexistent.com") is False

    def test_add_batch_empty(self, temp_db):
        """测试批量添加空列表"""
        count = NewsRepository.add_batch([])
        assert count == 0

    def test_mark_as_sent_empty(self, temp_db):
        """测试标记空列表"""
        count = NewsRepository.mark_as_sent([])
        assert count == 0
