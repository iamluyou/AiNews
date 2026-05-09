#!/usr/bin/env python3
"""
一次性执行爬虫任务（不启动定时调度）
"""
import sys
from pathlib import Path
from datetime import datetime

# 添加 src 到路径
src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from news_agent.config import get_config
from news_agent.llm import create_llm_from_config
from news_agent.notifiers import create_notifiers_from_config
from news_agent.pipeline import create_crawlers, fetch_all_news, process_and_notify
from news_agent.storage import init_db
from news_agent.utils.logger import get_logger, setup_logger

logger = get_logger("run_once")


def run_once():
    """执行一次完整任务"""
    logger.info("=" * 50)
    logger.info("开始执行一次性爬虫任务")
    logger.info("=" * 50)

    # 加载配置
    config = get_config()
    setup_logger(
        log_file=config.logging.file_path,
        level=config.logging.level,
    )

    # 初始化数据库
    init_db(config.database.path)

    # 通过工厂函数初始化组件
    crawlers = create_crawlers(config)
    notifiers = create_notifiers_from_config(config)
    llm = create_llm_from_config(config)

    # 1. 抓取新闻
    all_news = fetch_all_news(
        crawlers,
        max_concurrent=config.crawlers.max_concurrent,
        timeout=config.crawlers.timeout + 30,
    )

    if not all_news:
        logger.warning("没有抓取到任何新闻")
        return

    # 2. 处理与通知
    process_and_notify(all_news, notifiers, llm)

    logger.info("=" * 50)
    logger.info("任务执行完成")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_once()
