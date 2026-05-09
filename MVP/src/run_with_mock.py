#!/usr/bin/env python3
"""
使用 Mock 数据执行完整流程（测试通知和 LLM 功能）
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from news_agent.config import get_config
from news_agent.models.news import NewsItem
from news_agent.notifiers import create_notifiers_from_config
from news_agent.llm import create_llm_from_config
from news_agent.pipeline import process_and_notify
from news_agent.storage import init_db, NewsRepository
from news_agent.utils.logger import get_logger, setup_logger

logger = get_logger("run_mock")


def get_mock_news() -> list:
    """获取模拟新闻数据"""
    base_time = datetime.now()
    return [
        NewsItem(
            title="字节跳动发布豆包大模型最新版本，性能提升30%",
            url="https://example.com/news/1",
            source="模拟新闻源",
            publish_time=base_time - timedelta(minutes=10),
            ai_relevance_score=0.98,
        ),
        NewsItem(
            title="GPT-5 即将发布？OpenAI 召开重要发布会",
            url="https://example.com/news/2",
            source="模拟新闻源",
            publish_time=base_time - timedelta(minutes=30),
            ai_relevance_score=0.95,
        ),
        NewsItem(
            title="Anthropic 发布 Claude 3.5，支持长文本理解",
            url="https://example.com/news/3",
            source="模拟新闻源",
            publish_time=base_time - timedelta(hours=1),
            ai_relevance_score=0.92,
        ),
        NewsItem(
            title="深度学习在医疗影像诊断中的新突破",
            url="https://example.com/news/4",
            source="模拟新闻源",
            publish_time=base_time - timedelta(hours=2),
            ai_relevance_score=0.85,
        ),
        NewsItem(
            title="Python 3.14 新特性前瞻：性能优化与新语法",
            url="https://example.com/news/5",
            source="模拟新闻源",
            publish_time=base_time - timedelta(hours=3),
            ai_relevance_score=0.5,
        ),
    ]


def run_with_mock():
    """使用 Mock 数据执行完整流程"""
    logger.info("=" * 50)
    logger.info("开始执行 Mock 数据任务流程")
    logger.info("=" * 50)

    # 加载配置
    config = get_config()
    setup_logger(
        log_file=config.logging.file_path,
        level=config.logging.level,
    )

    # 初始化数据库
    init_db(config.database.path)

    # 获取 Mock 新闻
    all_news = get_mock_news()
    logger.info(f"使用 {len(all_news)} 条 Mock 新闻")

    # 按发布时间排序
    all_news.sort(
        key=lambda x: x.publish_time or x.created_at,
        reverse=True
    )

    # 存储到数据库
    NewsRepository.add_batch(all_news)
    logger.info("Mock 新闻已存储到数据库")

    # 通过工厂函数初始化组件
    notifiers = create_notifiers_from_config(config)
    llm = create_llm_from_config(config)

    # 发送通知（LLM 处理前的原始新闻）
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    for notifier in notifiers:
        try:
            notifier.send(all_news, title=f"Mock {notifier.default_title} - {now_str}")
            logger.info(f"✅ {notifier.name} 通知发送成功")
        except Exception as e:
            logger.error(f"❌ {notifier.name} 通知发送失败: {e}")

    # LLM 处理
    processed_news = all_news
    if llm:
        logger.info("正在使用 LLM 整理新闻...")
        try:
            processed_news = llm.process_news(all_news)
            logger.info(f"✅ LLM 处理完成，剩余 {len(processed_news)} 条新闻")
        except Exception as e:
            logger.error(f"❌ LLM 处理失败: {e}")
            processed_news = all_news

    logger.info("=" * 50)
    logger.info("Mock 任务执行完成")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_with_mock()
