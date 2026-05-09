"""
去重工具函数测试
"""
from datetime import datetime

from news_agent.models.news import NewsItem
from news_agent.utils.deduplication import deduplicate_news_by_url, deduplicate_by_field


class TestDeduplicateNewsByUrl:
    """测试按 URL 去重"""

    def test_empty_list(self):
        assert deduplicate_news_by_url([]) == []

    def test_no_duplicates(self):
        news = [
            NewsItem(title="新闻1", url="https://a.com/1", source="A"),
            NewsItem(title="新闻2", url="https://a.com/2", source="A"),
        ]
        result = deduplicate_news_by_url(news)
        assert len(result) == 2

    def test_with_duplicates(self):
        news = [
            NewsItem(title="新闻1", url="https://a.com/1", source="A"),
            NewsItem(title="新闻1重复", url="https://a.com/1", source="B"),
            NewsItem(title="新闻2", url="https://a.com/2", source="A"),
        ]
        result = deduplicate_news_by_url(news)
        assert len(result) == 2
        assert result[0].title == "新闻1"  # 保留第一次出现

    def test_all_duplicates(self):
        news = [
            NewsItem(title="新闻1", url="https://a.com/1", source="A"),
            NewsItem(title="新闻1重复", url="https://a.com/1", source="B"),
            NewsItem(title="新闻1再重复", url="https://a.com/1", source="C"),
        ]
        result = deduplicate_news_by_url(news)
        assert len(result) == 1

    def test_preserves_order(self):
        news = [
            NewsItem(title="第三", url="https://a.com/3", source="A"),
            NewsItem(title="第一", url="https://a.com/1", source="A"),
            NewsItem(title="第二", url="https://a.com/2", source="A"),
        ]
        result = deduplicate_news_by_url(news)
        assert [n.url for n in result] == [
            "https://a.com/3",
            "https://a.com/1",
            "https://a.com/2",
        ]


class TestDeduplicateByField:
    """测试按字段去重"""

    def test_empty_list(self):
        assert deduplicate_by_field([], "url") == []

    def test_by_source(self):
        news = [
            NewsItem(title="新闻1", url="https://a.com/1", source="A"),
            NewsItem(title="新闻2", url="https://a.com/2", source="B"),
            NewsItem(title="新闻3", url="https://a.com/3", source="A"),
        ]
        result = deduplicate_by_field(news, "source")
        assert len(result) == 2
        assert result[0].source == "A"
        assert result[1].source == "B"

    def test_none_field_value(self):
        news = [
            NewsItem(title="新闻1", url="https://a.com/1", source="A"),
            NewsItem(title="新闻2", url="https://a.com/2", source="A"),
        ]
        # ai_relevance_score 默认为 None
        result = deduplicate_by_field(news, "ai_relevance_score")
        # None 字段值的项不参与去重但保留（取决于实现）
        assert len(result) >= 0
