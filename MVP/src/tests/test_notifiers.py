"""
通知模块测试
"""
from datetime import datetime

from news_agent.notifiers.base import BaseNotifier
from news_agent.models.news import NewsItem


class MockNotifier(BaseNotifier):
    """模拟通知器用于测试"""

    name = "mock"

    def __init__(self):
        self.sent_count = 0
        self.last_news_list = None
        self.last_title = None

    def send(self, news_list, title=""):
        self.sent_count += 1
        self.last_news_list = news_list
        self.last_title = title
        return True


class TestBaseNotifier:
    """测试通知基类"""

    def test_format_news_list(self):
        """测试新闻列表格式化"""
        notifier = MockNotifier()

        news = NewsItem(
            title="测试新闻",
            url="https://example.com/test",
            source="测试",
            publish_time=datetime(2024, 1, 1, 12, 0),
        )

        formatted = notifier.format_news_list([news])
        assert "测试新闻" in formatted
        assert "https://example.com/test" in formatted
        assert "2024-01-01 12:00" in formatted

    def test_send(self):
        """测试发送通知"""
        notifier = MockNotifier()

        news = NewsItem(
            title="测试新闻",
            url="https://example.com/test",
            source="测试",
        )

        result = notifier.send([news], title="测试标题")
        assert result is True
        assert notifier.sent_count == 1
        assert notifier.last_title == "测试标题"
        assert len(notifier.last_news_list) == 1


class TestNotifiers:
    """测试通知器"""

    def test_feishu_notifier_init(self):
        """测试飞书通知器初始化"""
        from news_agent.notifiers.feishu import FeishuNotifier

        notifier = FeishuNotifier(webhook_urls=["https://example.com/webhook"])
        assert notifier is not None
        assert notifier.name == "feishu"

    def test_email_notifier_init(self):
        """测试邮件通知器初始化"""
        from news_agent.notifiers.email_163 import Email163Notifier

        notifier = Email163Notifier(
            sender="test@163.com",
            password="test-password",
            recipients=["recipient@example.com"],
        )
        assert notifier is not None
        assert notifier.name == "email_163"
