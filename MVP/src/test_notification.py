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
from news_agent.notifiers import create_notifiers_from_config
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


def main():
    """主函数"""
    config = get_config()
    setup_logger(level="DEBUG")

    logger.info("=" * 50)
    logger.info("开始测试通知功能")
    logger.info("=" * 50)

    news_list = get_mock_news()
    logger.info(f"使用 {len(news_list)} 条模拟新闻进行测试")

    # 通过工厂函数创建通知器
    notifiers = create_notifiers_from_config(config)

    if not notifiers:
        logger.warning("没有可用的通知器，请检查配置")
        return

    success_count = 0
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    for notifier in notifiers:
        try:
            logger.info(f"正在测试 {notifier.name} 通知...")
            result = notifier.send(
                news_list,
                title=f"测试 {notifier.default_title} - {now_str}",
            )
            if result:
                logger.info(f"✅ {notifier.name} 通知发送成功")
                success_count += 1
            else:
                logger.error(f"❌ {notifier.name} 通知发送失败")
        except Exception as e:
            logger.error(f"❌ {notifier.name} 通知异常: {e}")

    logger.info("=" * 50)
    logger.info(f"测试完成: {success_count}/{len(notifiers)} 成功")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
