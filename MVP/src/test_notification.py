#!/usr/bin/env python3
"""
测试通知功能（使用模拟数据，不实际爬取）
"""
import sys
from pathlib import Path
from datetime import datetime

# 添加 src 到路径
src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from news_agent.config import get_config
from news_agent.models.news import NewsItem
from news_agent.notifiers import FeishuNotifier, Email163Notifier
from news_agent.utils.logger import get_logger, setup_logger

logger = get_logger("test_notification")


def get_mock_news() -> list:
    """获取模拟新闻数据"""
    return [
        NewsItem(
            title="AI 大模型最新进展：GPT-5 即将发布",
            url="https://example.com/news/1",
            source="测试来源",
            publish_time=datetime.now(),
            ai_relevance_score=0.95,
        ),
        NewsItem(
            title="深度学习在医疗领域的应用",
            url="https://example.com/news/2",
            source="测试来源",
            publish_time=datetime.now(),
            ai_relevance_score=0.85,
        ),
        NewsItem(
            title="Python 3.13 新特性介绍",
            url="https://example.com/news/3",
            source="测试来源",
            publish_time=datetime.now(),
            ai_relevance_score=0.6,
        ),
    ]


def test_feishu(news_list):
    """测试飞书通知"""
    config = get_config()
    if not config.feishu.enabled or not config.feishu.webhook_url:
        logger.warning("飞书通知未配置，跳过测试")
        return False

    logger.info("正在测试飞书通知...")
    try:
        notifier = FeishuNotifier(config.feishu.webhook_url)
        result = notifier.send(news_list, title=f"测试通知 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        if result:
            logger.info("✅ 飞书通知发送成功")
            return True
        else:
            logger.error("❌ 飞书通知发送失败")
            return False
    except Exception as e:
        logger.error(f"❌ 飞书通知异常: {e}")
        return False


def test_email(news_list):
    """测试邮件通知"""
    config = get_config()
    if not config.email_163.enabled or not config.email_163.sender:
        logger.warning("邮件通知未配置，跳过测试")
        return False

    logger.info("正在测试邮件通知...")
    try:
        notifier = Email163Notifier(
            sender=config.email_163.sender,
            password=config.email_163.password,
            recipients=config.email_163.recipients,
        )
        result = notifier.send(news_list, title=f"AI 新闻整理测试 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        if result:
            logger.info("✅ 邮件通知发送成功")
            return True
        else:
            logger.error("❌ 邮件通知发送失败")
            return False
    except Exception as e:
        logger.error(f"❌ 邮件通知异常: {e}")
        return False


def main():
    """主函数"""
    config = get_config()
    setup_logger(level="DEBUG")

    logger.info("=" * 50)
    logger.info("开始测试通知功能")
    logger.info("=" * 50)

    news_list = get_mock_news()
    logger.info(f"使用 {len(news_list)} 条模拟新闻进行测试")

    success_count = 0
    total_count = 0

    # 测试飞书
    total_count += 1
    if test_feishu(news_list):
        success_count += 1

    # 测试邮件
    total_count += 1
    if test_email(news_list):
        success_count += 1

    logger.info("=" * 50)
    logger.info(f"测试完成: {success_count}/{total_count} 成功")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
