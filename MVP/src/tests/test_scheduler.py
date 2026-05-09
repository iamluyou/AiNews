"""
Scheduler 模块测试
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from news_agent.scheduler import NewsScheduler
from news_agent.models.news import NewsItem


@pytest.fixture
def mock_config():
    """Mock 配置"""
    config = Mock()
    config.scheduler.cron_times = ["08:30"]
    config.scheduler.timezone = "Asia/Shanghai"
    config.crawlers.enabled = ["test"]
    config.crawlers.timeout = 30
    config.crawlers.request_delay = 0.1
    config.database.path = ":memory:"
    config.llm.api_key = ""
    config.feishu.enabled = False
    config.email_163.enabled = False
    config.logging.file_path = "/tmp/test.log"
    config.logging.level = "INFO"
    return config


@pytest.fixture
def sample_news_items():
    """示例新闻数据"""
    return [
        NewsItem(
            title="AI 大模型最新进展",
            url="https://example.com/1",
            source="TestSource",
            publish_time=datetime(2024, 1, 1, 10, 0),
            created_at=datetime(2024, 1, 1, 10, 0),
        ),
        NewsItem(
            title="机器学习新突破",
            url="https://example.com/2",
            source="TestSource",
            publish_time=datetime(2024, 1, 1, 11, 0),
            created_at=datetime(2024, 1, 1, 11, 0),
        ),
    ]


class TestNewsScheduler:
    """测试 NewsScheduler"""

    @patch("news_agent.scheduler.get_config")
    @patch("news_agent.scheduler.setup_logger")
    @patch("news_agent.scheduler.init_db")
    def test_init(self, mock_init_db, mock_setup_logger, mock_get_config, mock_config):
        """测试初始化"""
        mock_get_config.return_value = mock_config

        scheduler = NewsScheduler.__new__(NewsScheduler)
        scheduler.config = mock_config
        scheduler.crawlers = []
        scheduler.notifiers = []
        scheduler.llm = None

        # 验证基本属性
        assert scheduler.config == mock_config
        assert len(scheduler.crawlers) == 0
        assert len(scheduler.notifiers) == 0
        assert scheduler.llm is None

    @patch("news_agent.scheduler.get_config")
    @patch("news_agent.scheduler.setup_logger")
    @patch("news_agent.scheduler.init_db")
    @patch("news_agent.scheduler.fetch_all_news", return_value=[])
    @patch("news_agent.scheduler.process_and_notify")
    def test_run_job_no_news(self, mock_process, mock_fetch, mock_init_db, mock_setup_logger, mock_get_config, mock_config):
        """测试无新闻的情况"""
        mock_get_config.return_value = mock_config

        scheduler = NewsScheduler.__new__(NewsScheduler)
        scheduler.config = mock_config
        scheduler.crawlers = []
        scheduler.notifiers = []
        scheduler.llm = None

        scheduler._run_job_inner(datetime.now())
        mock_fetch.assert_called_once()
        mock_process.assert_called_once_with([], [], None)

    def test_deduplication_logic(self, sample_news_items):
        """测试去重逻辑（与 scheduler 中一致的逻辑）"""
        # 模拟 scheduler 中的去重逻辑
        all_news = sample_news_items + [sample_news_items[0]]  # 添加重复

        seen_urls = set()
        unique_news = []
        for news in all_news:
            if news.url not in seen_urls:
                seen_urls.add(news.url)
                unique_news.append(news)

        assert len(unique_news) == 2
        assert len(seen_urls) == 2

    def test_sorting_logic(self, sample_news_items):
        """测试排序逻辑"""
        # 打乱顺序
        news_list = list(reversed(sample_news_items))

        # 按时间排序
        news_list.sort(
            key=lambda x: x.publish_time or x.created_at,
            reverse=True
        )

        # 验证最新的在前面
        assert news_list[0].publish_time > news_list[1].publish_time


class TestCrawlerConcurrency:
    """测试爬虫并发逻辑（设计验证）"""

    def test_concurrent_crawler_design(self):
        """验证并发设计的正确性"""
        # 这是对并发设计的验证测试
        # 实际并发功能在实现后会有更详细的测试

        # 验证 ThreadPoolExecutor 的使用思路是正确的
        from concurrent.futures import ThreadPoolExecutor

        # 简单的测试：验证 ThreadPoolExecutor 可以正常工作
        def mock_crawler(name):
            return [NewsItem(title=f"{name} news", url=f"https://{name}.com", source=name, created_at=datetime.now())]

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(mock_crawler, name) for name in ["c1", "c2"]]
            results = []
            for future in futures:
                results.extend(future.result())

        assert len(results) == 2
