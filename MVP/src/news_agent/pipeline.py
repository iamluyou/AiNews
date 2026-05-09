"""新闻处理流水线：抓取 → 去重 → 存储 → LLM整理 → 通知"""

from datetime import datetime
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import get_config
from .crawlers import CRAWLER_REGISTRY, BaseCrawler
from .llm import BaseLLM
from .models.news import NewsItem
from .notifiers import BaseNotifier
from .storage import NewsRepository
from .utils.logger import get_logger
from .utils import deduplicate_news_by_url

logger = get_logger(__name__)


def create_crawlers(config=None) -> List[BaseCrawler]:
    """根据配置创建爬虫列表"""
    if config is None:
        config = get_config()
    crawlers = []
    crawler_config = config.crawlers
    for crawler_name in crawler_config.enabled:
        if crawler_name in CRAWLER_REGISTRY:
            crawler_cls = CRAWLER_REGISTRY[crawler_name]
            crawler = crawler_cls(
                timeout=crawler_config.timeout,
                request_delay=crawler_config.request_delay,
            )
            crawlers.append(crawler)
            logger.info(f"Loaded crawler: {crawler_name}")
    return crawlers


def fetch_all_news(crawlers: List[BaseCrawler], max_concurrent: int = 3, timeout: int = 90) -> List[NewsItem]:
    """执行所有爬虫，并发抓取新闻"""
    all_news: List[NewsItem] = []
    max_workers = min(max_concurrent, len(crawlers))

    if max_workers > 1 and len(crawlers) > 1:
        logger.info(f"Starting concurrent crawling with {max_workers} workers")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_crawler = {
                executor.submit(crawler.fetch): crawler
                for crawler in crawlers
            }
            for future in as_completed(future_to_crawler, timeout=timeout):
                crawler = future_to_crawler[future]
                try:
                    news_list = future.result(timeout=10)
                    all_news.extend(news_list)
                except Exception as e:
                    logger.error(f"Crawler {crawler.name} failed: {e}")
    else:
        logger.info("Starting sequential crawling")
        for crawler in crawlers:
            try:
                news_list = crawler.fetch()
                all_news.extend(news_list)
            except Exception as e:
                logger.error(f"Crawler {crawler.name} failed: {e}")

    return all_news


def process_and_notify(
    news_list: List[NewsItem],
    notifiers: List[BaseNotifier],
    llm: Optional[BaseLLM] = None,
) -> None:
    """处理新闻流水线：去重 → 存储 → 过滤 → LLM → 通知 → 标记"""
    if not news_list:
        logger.warning("No news fetched")
        return

    logger.info(f"Fetched total {len(news_list)} news")

    # 1. 内存去重
    news_list = deduplicate_news_by_url(news_list)
    logger.info(f"内存去重后剩余 {len(news_list)} 条新闻")

    # 2. 按发布时间排序
    news_list.sort(key=lambda x: x.publish_time or x.created_at, reverse=True)

    # 3. 存储到数据库
    NewsRepository.add_batch(news_list)
    logger.info("新闻已存储到数据库")

    # 4. 过滤已发送的新闻
    unsent_news = [n for n in news_list if not NewsRepository.is_sent(n.url)]
    logger.info(f"共抓取到 {len(news_list)} 条新闻，其中 {len(unsent_news)} 条未发送")

    # 5. 全部已发送则发提示
    if not unsent_news:
        logger.info("所有新闻都是已发送过的，发送提示消息")
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        for notifier in notifiers:
            try:
                notifier.send(
                    [], title=f"{notifier.default_title} - {now_str}",
                    used_llm=False, custom_message="最近没有未推送的新闻了",
                )
            except Exception as e:
                logger.error(f"{notifier.name} 提示消息发送失败: {e}")
        return

    # 6. LLM 整理
    processed_news = unsent_news
    used_llm = False
    if llm:
        try:
            processed_news = llm.process_news(unsent_news)
            used_llm = True
            logger.info(f"After LLM processing: {len(processed_news)} news")
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")

    # 7. 发送通知
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    for notifier in notifiers:
        try:
            notifier.send(
                processed_news,
                title=f"{notifier.default_title} - {now_str}",
                used_llm=used_llm,
            )
            logger.info(f"{notifier.name} 通知发送成功")
        except Exception as e:
            logger.error(f"Failed to send {notifier.name} notification: {e}")

    # 8. 标记已发送
    if processed_news:
        sent_urls = [n.url for n in processed_news]
        NewsRepository.mark_as_sent(sent_urls)
        logger.info(f"已标记 {len(sent_urls)} 条新闻为已发送")
