"""
通知器增强测试（消息构建，不实际发送）
"""
from datetime import datetime
from unittest.mock import patch, MagicMock

from news_agent.models.news import NewsItem
from news_agent.notifiers import (
    BaseNotifier,
    FeishuNotifier,
    Email163Notifier,
    NOTIFIER_REGISTRY,
    create_notifiers_from_config,
)


class TestNotifierRegistry:
    """测试通知器注册表"""

    def test_registry_contains_all_notifiers(self):
        assert "feishu" in NOTIFIER_REGISTRY
        assert "email_163" in NOTIFIER_REGISTRY

    def test_registry_classes(self):
        assert NOTIFIER_REGISTRY["feishu"] is FeishuNotifier
        assert NOTIFIER_REGISTRY["email_163"] is Email163Notifier


class TestFeishuNotifier:
    """测试飞书通知器"""

    def test_init_with_list(self):
        notifier = FeishuNotifier(webhook_urls=["https://example.com/1", "https://example.com/2"])
        assert len(notifier.webhook_urls) == 2

    def test_init_with_string_converts_to_list(self):
        notifier = FeishuNotifier(webhook_urls="https://example.com/1")
        assert isinstance(notifier.webhook_urls, list)
        assert len(notifier.webhook_urls) == 1

    def test_default_title(self):
        notifier = FeishuNotifier(webhook_urls=["https://example.com/1"])
        assert notifier.default_title == "新闻推送"

    def test_build_text_message_with_llm(self):
        notifier = FeishuNotifier(webhook_urls=["https://example.com/1"])
        news = [
            NewsItem(
                title="AI 大模型突破",
                url="https://example.com/1",
                source="TestSource",
                publish_time=datetime(2024, 1, 1, 12, 0),
            )
        ]
        message = notifier._build_text_message(news, "测试推送", used_llm=True)
        assert "🤖 AI 智能筛选" in message
        assert "AI 大模型突破" in message
        assert "2024-01-01 12:00" in message

    def test_build_text_message_without_llm(self):
        notifier = FeishuNotifier(webhook_urls=["https://example.com/1"])
        news = [
            NewsItem(title="普通新闻", url="https://example.com/1", source="TestSource"),
        ]
        message = notifier._build_text_message(news, "测试推送", used_llm=False)
        assert "📋 关键词筛选" in message

    def test_send_empty_without_custom_message(self):
        notifier = FeishuNotifier(webhook_urls=["https://example.com/1"])
        result = notifier.send([], title="测试")
        assert result is False

    @patch("news_agent.notifiers.feishu.requests.post")
    def test_send_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        notifier = FeishuNotifier(webhook_urls=["https://example.com/webhook"])
        news = [NewsItem(title="测试", url="https://example.com", source="S")]
        result = notifier.send(news, title="测试推送", used_llm=True)
        assert result is True
        assert mock_post.call_count == 1

    @patch("news_agent.notifiers.feishu.requests.post")
    def test_send_to_multiple_webhooks(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        notifier = FeishuNotifier(
            webhook_urls=["https://example.com/1", "https://example.com/2"]
        )
        news = [NewsItem(title="测试", url="https://example.com", source="S")]
        result = notifier.send(news, title="测试推送")
        assert result is True
        assert mock_post.call_count == 2

    @patch("news_agent.notifiers.feishu.requests.post")
    def test_send_partial_failure(self, mock_post):
        mock_response_ok = MagicMock()
        mock_response_ok.json.return_value = {"code": 0}
        mock_response_ok.raise_for_status = MagicMock()

        mock_response_fail = MagicMock()
        mock_response_fail.json.return_value = {"code": 19001, "msg": "fail"}
        mock_response_fail.raise_for_status = MagicMock()

        mock_post.side_effect = [mock_response_ok, mock_response_fail]

        notifier = FeishuNotifier(
            webhook_urls=["https://example.com/1", "https://example.com/2"]
        )
        news = [NewsItem(title="测试", url="https://example.com", source="S")]
        result = notifier.send(news, title="测试推送")
        assert result is False  # 部分失败返回 False


class TestEmail163Notifier:
    """测试邮件通知器"""

    def test_init(self):
        notifier = Email163Notifier(
            sender="test@163.com",
            password="pass",
            recipients=["a@b.com", "c@d.com"],
        )
        assert notifier.name == "email_163"
        assert notifier.default_title == "AI 新闻整理"
        assert len(notifier.recipients) == 2

    def test_send_empty_without_custom_message(self):
        notifier = Email163Notifier(
            sender="test@163.com",
            password="pass",
            recipients=["a@b.com"],
        )
        result = notifier.send([], title="测试")
        assert result is False

    def test_send_no_recipients(self):
        notifier = Email163Notifier(
            sender="test@163.com",
            password="pass",
            recipients=[],
        )
        news = [NewsItem(title="测试", url="https://example.com", source="S")]
        result = notifier.send(news, title="测试")
        assert result is False

    def test_build_html_with_llm(self):
        notifier = Email163Notifier(
            sender="test@163.com",
            password="pass",
            recipients=["a@b.com"],
        )
        news = [
            NewsItem(
                title="AI 大模型",
                url="https://example.com",
                source="TestSource",
                ai_relevance_score=0.9,
            )
        ]
        html = notifier._build_html(news, "测试推送", used_llm=True)
        assert "🤖 AI 智能筛选" in html
        assert "AI 大模型" in html
        assert "90.00%" in html

    def test_build_html_without_llm(self):
        notifier = Email163Notifier(
            sender="test@163.com",
            password="pass",
            recipients=["a@b.com"],
        )
        news = [NewsItem(title="普通", url="https://example.com", source="S")]
        html = notifier._build_html(news, "测试推送", used_llm=False)
        assert "📋 关键词筛选" in html

    def test_build_custom_message_html(self):
        notifier = Email163Notifier(
            sender="test@163.com",
            password="pass",
            recipients=["a@b.com"],
        )
        html = notifier._build_custom_message_html("标题", "没有新新闻")
        assert "没有新新闻" in html
        assert "标题" in html


class TestCreateNotifiersFromConfig:
    """测试工厂函数"""

    def test_creates_feishu_notifier(self):
        mock_config = MagicMock()
        mock_config.feishu.enabled = True
        mock_config.feishu.webhook_urls = ["https://example.com/webhook"]
        mock_config.email_163.enabled = False
        mock_config.email_163.sender = ""

        notifiers = create_notifiers_from_config(mock_config)
        assert len(notifiers) == 1
        assert isinstance(notifiers[0], FeishuNotifier)

    def test_creates_both_notifiers(self):
        mock_config = MagicMock()
        mock_config.feishu.enabled = True
        mock_config.feishu.webhook_urls = ["https://example.com/webhook"]
        mock_config.email_163.enabled = True
        mock_config.email_163.sender = "test@163.com"
        mock_config.email_163.sender_name = "Test"
        mock_config.email_163.password = "pass"
        mock_config.email_163.recipients = ["a@b.com"]

        notifiers = create_notifiers_from_config(mock_config)
        assert len(notifiers) == 2

    def test_creates_no_notifiers(self):
        mock_config = MagicMock()
        mock_config.feishu.enabled = False
        mock_config.feishu.webhook_urls = []
        mock_config.email_163.enabled = False
        mock_config.email_163.sender = ""

        notifiers = create_notifiers_from_config(mock_config)
        assert len(notifiers) == 0
