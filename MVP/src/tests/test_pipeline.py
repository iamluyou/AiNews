"""Pipeline 模块测试：抓取、处理、通知流水线"""
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from news_agent.models.news import NewsItem
from news_agent.pipeline import create_crawlers, fetch_all_news, process_and_notify


def _make_news(url="http://test.com/1", title="Test News", source="test"):
    return NewsItem(
        url=url,
        title=title,
        source=source,
        summary="summary",
        publish_time=datetime.now(),
    )


class TestCreateCrawlers:

    @patch("news_agent.pipeline.get_config")
    def test_creates_enabled_crawlers(self, mock_get_config):
        mock_config = Mock()
        mock_config.crawlers.enabled = ["kr36", "aiera"]
        mock_config.crawlers.timeout = 30
        mock_config.crawlers.request_delay = 0.5
        mock_get_config.return_value = mock_config

        crawlers = create_crawlers(mock_config)
        assert len(crawlers) == 2
        assert crawlers[0].name == "kr36"
        assert crawlers[1].name == "aiera"

    @patch("news_agent.pipeline.get_config")
    def test_skips_unknown_crawlers(self, mock_get_config):
        mock_config = Mock()
        mock_config.crawlers.enabled = ["kr36", "nonexistent"]
        mock_config.crawlers.timeout = 30
        mock_config.crawlers.request_delay = 0.5
        mock_get_config.return_value = mock_config

        crawlers = create_crawlers(mock_config)
        assert len(crawlers) == 1

    def test_empty_config(self):
        mock_config = Mock()
        mock_config.crawlers.enabled = []
        mock_config.crawlers.timeout = 30
        mock_config.crawlers.request_delay = 0.5

        crawlers = create_crawlers(mock_config)
        assert len(crawlers) == 0


class TestFetchAllNews:

    def test_sequential_fetch(self):
        crawler1 = Mock()
        crawler1.name = "c1"
        crawler1.fetch.return_value = [_make_news(url="http://1.com")]

        crawler2 = Mock()
        crawler2.name = "c2"
        crawler2.fetch.return_value = [_make_news(url="http://2.com")]

        result = fetch_all_news([crawler1, crawler2], max_concurrent=1)
        assert len(result) == 2

    def test_concurrent_fetch(self):
        crawler1 = Mock()
        crawler1.name = "c1"
        crawler1.fetch.return_value = [_make_news(url="http://1.com")]

        crawler2 = Mock()
        crawler2.name = "c2"
        crawler2.fetch.return_value = [_make_news(url="http://2.com")]

        result = fetch_all_news([crawler1, crawler2], max_concurrent=3)
        assert len(result) == 2

    def test_fetch_with_error(self):
        crawler1 = Mock()
        crawler1.name = "c1"
        crawler1.fetch.return_value = [_make_news()]

        crawler2 = Mock()
        crawler2.name = "c2"
        crawler2.fetch.side_effect = Exception("fetch error")

        result = fetch_all_news([crawler1, crawler2], max_concurrent=1)
        assert len(result) == 1

    def test_empty_crawlers(self):
        result = fetch_all_news([], max_concurrent=1)
        assert result == []


class TestProcessAndNotify:

    @patch("news_agent.pipeline.NewsRepository")
    @patch("news_agent.pipeline.deduplicate_news_by_url", side_effect=lambda x: x)
    def test_empty_news_returns_early(self, mock_dedup, mock_repo):
        result = process_and_notify([], notifiers=[], llm=None)
        assert result is None
        mock_dedup.assert_not_called()

    @patch("news_agent.pipeline.NewsRepository")
    @patch("news_agent.pipeline.deduplicate_news_by_url", side_effect=lambda x: x)
    def test_all_sent_sends_hint(self, mock_dedup, mock_repo):
        mock_repo.is_sent.return_value = True
        mock_repo.add_batch = Mock()
        notifier = Mock()
        notifier.default_title = "Test"

        news = [_make_news()]
        process_and_notify(news, notifiers=[notifier], llm=None)
        notifier.send.assert_called_once()
        call_kwargs = notifier.send.call_args
        assert "最近没有未推送的新闻了" in str(call_kwargs)

    @patch("news_agent.pipeline.NewsRepository")
    @patch("news_agent.pipeline.deduplicate_news_by_url", side_effect=lambda x: x)
    def test_unsent_news_gets_notified(self, mock_dedup, mock_repo):
        mock_repo.is_sent.return_value = False
        mock_repo.add_batch = Mock()
        mock_repo.mark_as_sent = Mock()
        notifier = Mock()
        notifier.default_title = "Test"

        news = [_make_news()]
        process_and_notify(news, notifiers=[notifier], llm=None)
        notifier.send.assert_called_once()
        mock_repo.mark_as_sent.assert_called_once()

    @patch("news_agent.pipeline.NewsRepository")
    @patch("news_agent.pipeline.deduplicate_news_by_url", side_effect=lambda x: x)
    def test_llm_processing(self, mock_dedup, mock_repo):
        mock_repo.is_sent.return_value = False
        mock_repo.add_batch = Mock()
        mock_repo.mark_as_sent = Mock()

        llm = Mock()
        processed = [_make_news(url="http://processed.com")]
        llm.process_news.return_value = processed

        notifier = Mock()
        notifier.default_title = "Test"

        news = [_make_news()]
        process_and_notify(news, notifiers=[notifier], llm=llm)
        llm.process_news.assert_called_once()
        mock_repo.mark_as_sent.assert_called_once()
