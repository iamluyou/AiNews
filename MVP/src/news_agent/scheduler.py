from datetime import datetime
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_config
from .crawlers import CRAWLER_REGISTRY, BaseCrawler
from .llm import OpenAIClient, BaseLLM
from .models.news import NewsItem
from .notifiers import FeishuNotifier, Email163Notifier, BaseNotifier
from .storage import init_db, NewsRepository
from .utils.logger import get_logger, setup_logger
from .utils import deduplicate_news_by_url

logger = get_logger(__name__)


class NewsScheduler:
    """新闻调度器"""

    def __init__(self):
        self.config = get_config()
        self._setup_logging()
        self._init_database()
        self.scheduler = BlockingScheduler(timezone=self.config.scheduler.timezone)
        self.crawlers: List[BaseCrawler] = []
        self.notifiers: List[BaseNotifier] = []
        self.llm: Optional[BaseLLM] = None
        self._init_components()

    def _setup_logging(self):
        """配置日志"""
        setup_logger(
            log_file=self.config.logging.file_path,
            level=self.config.logging.level,
        )

    def _init_database(self):
        """初始化数据库"""
        init_db(self.config.database.path)

    def _init_components(self):
        """初始化组件"""
        # 初始化爬虫
        crawler_config = self.config.crawlers
        for crawler_name in crawler_config.enabled:
            if crawler_name in CRAWLER_REGISTRY:
                crawler_cls = CRAWLER_REGISTRY[crawler_name]
                crawler = crawler_cls(
                    timeout=crawler_config.timeout,
                    request_delay=crawler_config.request_delay,
                )
                self.crawlers.append(crawler)
                logger.info(f"Loaded crawler: {crawler_name}")

        # 初始化通知器
        if self.config.feishu.enabled and self.config.feishu.webhook_url:
            self.notifiers.append(FeishuNotifier(self.config.feishu.webhook_url))
            logger.info("Loaded Feishu notifier")

        if self.config.email_163.enabled and self.config.email_163.sender:
            self.notifiers.append(
                Email163Notifier(
                    sender=self.config.email_163.sender,
                    sender_name=self.config.email_163.sender_name,
                    password=self.config.email_163.password,
                    recipients=self.config.email_163.recipients,
                )
            )
            logger.info("Loaded Email163 notifier")

        # 初始化 LLM
        if self.config.llm.api_key:
            self.llm = OpenAIClient(
                base_url=self.config.llm.base_url,
                api_key=self.config.llm.api_key,
                model=self.config.llm.model,
                max_retries=self.config.llm.max_retries,
                timeout=self.config.llm.timeout,
                ranking_prompt=self.config.llm.ranking_prompt,
                use_llm_for_ranking=self.config.llm.use_llm_for_ranking,
                batch_size=self.config.llm.batch_size,
                top_n_per_batch=self.config.llm.top_n_per_batch,
                final_top_n=self.config.llm.final_top_n,
                fallback_per_source=self.config.llm.fallback_per_source,
            )
            logger.info("Loaded LLM client")

    def _fetch_crawler(self, crawler: BaseCrawler) -> List[NewsItem]:
        """执行单个爬虫（用于并发执行）"""
        logger.info(f"Starting crawler: {crawler.name}")
        news_list = crawler.fetch()
        logger.info(f"Crawler {crawler.name} fetched {len(news_list)} news")
        return news_list

    def run_job(self):
        """执行一次完整任务"""
        logger.info("=" * 50)
        logger.info("Starting news collection job")
        start_time = datetime.now()

        all_news: List[NewsItem] = []

        # 1. 执行所有爬虫（支持并发）
        max_workers = min(self.config.crawlers.max_concurrent, len(self.crawlers))
        if max_workers > 1 and len(self.crawlers) > 1:
            logger.info(f"Starting concurrent crawling with {max_workers} workers")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有爬虫任务
                future_to_crawler = {
                    executor.submit(self._fetch_crawler, crawler): crawler
                    for crawler in self.crawlers
                }

                # 收集结果
                for future in as_completed(future_to_crawler):
                    crawler = future_to_crawler[future]
                    try:
                        news_list = future.result()
                        all_news.extend(news_list)
                    except Exception as e:
                        logger.error(f"Crawler {crawler.name} failed: {e}")
        else:
            # 回退到串行执行
            logger.info("Starting sequential crawling")
            for crawler in self.crawlers:
                try:
                    news_list = crawler.fetch()
                    all_news.extend(news_list)
                except Exception as e:
                    logger.error(f"Crawler {crawler.name} failed: {e}")

        if not all_news:
            logger.warning("No news fetched")
            return

        logger.info(f"Fetched total {len(all_news)} news")

        # 2. 内存去重（按 URL）
        all_news = deduplicate_news_by_url(all_news)
        logger.info(f"内存去重后剩余 {len(all_news)} 条新闻")

        # 3. 按发布时间排序
        all_news.sort(
            key=lambda x: x.publish_time or x.created_at,
            reverse=True
        )

        # 4. 存储到数据库
        NewsRepository.add_batch(all_news)
        logger.info("新闻已存储到数据库")

        # 5. 过滤掉已发送的新闻
        unsent_news = []
        for news in all_news:
            if not NewsRepository.is_sent(news.url):
                unsent_news.append(news)

        logger.info(f"共抓取到 {len(all_news)} 条新闻，其中 {len(unsent_news)} 条未发送")

        # 6. 如果所有新闻都是已发送的，发送提示消息
        if not unsent_news:
            logger.info("所有新闻都是已发送过的，发送提示消息")
            for notifier in self.notifiers:
                try:
                    notifier.send([], title=f"新闻推送 - {datetime.now().strftime('%Y-%m-%d %H:%M')}", used_llm=False, custom_message="最近没有未推送的新闻了")
                    logger.info(f"{notifier.name} 提示消息发送成功")
                except Exception as e:
                    logger.error(f"{notifier.name} 提示消息发送失败: {e}")
            logger.info("=" * 50)
            logger.info("Job completed")
            logger.info("=" * 50)
            return

        # 7. 只处理未发送的新闻
        all_news = unsent_news

        # 8. 使用 LLM 整理和排序
        processed_news = all_news
        used_llm = False
        if self.llm:
            try:
                processed_news = self.llm.process_news(all_news)
                used_llm = True
                logger.info(f"After LLM processing: {len(processed_news)} news")
            except Exception as e:
                logger.error(f"LLM processing failed: {e}")

        # 9. 发送通知（都使用整理后的新闻）
        for notifier in self.notifiers:
            try:
                if isinstance(notifier, FeishuNotifier):
                    notifier.send(processed_news, title=f"新闻推送 - {datetime.now().strftime('%Y-%m-%d %H:%M')}", used_llm=used_llm)
                elif isinstance(notifier, Email163Notifier):
                    notifier.send(processed_news, title=f"AI 新闻整理 - {datetime.now().strftime('%Y-%m-%d %H:%M')}", used_llm=used_llm)
                logger.info(f"{notifier.name} 通知发送成功")
            except Exception as e:
                logger.error(f"Failed to send {notifier.name} notification: {e}")

        # 10. 标记新闻为已发送
        if processed_news:
            sent_urls = [news.url for news in processed_news]
            NewsRepository.mark_as_sent(sent_urls)
            logger.info(f"已标记 {len(sent_urls)} 条新闻为已发送")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Job completed in {duration:.2f} seconds")
        logger.info("=" * 50)

    def start(self):
        """启动调度器"""
        # 添加定时任务
        for cron_time in self.config.scheduler.cron_times:
            hour, minute = cron_time.split(":")
            self.scheduler.add_job(
                self.run_job,
                trigger=CronTrigger(hour=int(hour), minute=int(minute)),
                name=f"NewsJob-{cron_time}",
                misfire_grace_time=1800,  # 错过任务宽限时间：30分钟
                coalesce=True,  # 合并错过的任务，只执行一次
                max_instances=1,  # 同时最多运行1个实例
            )
            logger.info(f"Scheduled job at {cron_time}")

        logger.info("Scheduler started. Press Ctrl+C to stop.")
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")


def main():
    """主函数"""
    scheduler = NewsScheduler()
    scheduler.start()


if __name__ == "__main__":
    main()
