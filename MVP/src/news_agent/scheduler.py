from datetime import datetime
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_config
from .crawlers import CRAWLER_REGISTRY, BaseCrawler
from .llm import create_llm_from_config, BaseLLM
from .models.news import NewsItem
from .notifiers import create_notifiers_from_config, BaseNotifier
from .storage import init_db, NewsRepository
from .utils.logger import get_logger, setup_logger
from .utils import deduplicate_news_by_url

logger = get_logger(__name__)

# 全局超时标志
_job_timed_out = False

# 休眠检测：记录上次心跳时间
_last_heartbeat = time.time()
_HEARTBEAT_INTERVAL = 30  # 心跳间隔（秒）


def _timeout_handler(signum, frame):
    """SIGALRM 信号处理器"""
    global _job_timed_out
    _job_timed_out = True
    raise TimeoutError("Job execution timed out")


def _check_sleep_recovery(check_interval: int = 60, sleep_threshold: int = 120):
    """检测系统从休眠中恢复，返回是否刚从休眠中唤醒

    Args:
        check_interval: 正常情况下两次检查的时间差（秒）
        sleep_threshold: 超过此时间差认为系统休眠过（秒）
    """
    global _last_heartbeat
    now = time.time()
    elapsed = now - _last_heartbeat

    if elapsed > sleep_threshold:
        logger.warning(f"System sleep detected! Time gap: {elapsed:.0f}s ({elapsed/3600:.1f}h)")
        _last_heartbeat = now
        return True

    _last_heartbeat = now
    return False


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

        # 初始化通知器（通过工厂函数）
        self.notifiers = create_notifiers_from_config(self.config)

        # 初始化 LLM（通过工厂函数）
        self.llm = create_llm_from_config(self.config)

    def _fetch_crawler(self, crawler: BaseCrawler) -> List[NewsItem]:
        """执行单个爬虫（用于并发执行）"""
        logger.info(f"Starting crawler: {crawler.name}")
        news_list = crawler.fetch()
        logger.info(f"Crawler {crawler.name} fetched {len(news_list)} news")
        return news_list

    def run_job(self):
        """执行一次完整任务（带超时保护）"""
        global _job_timed_out

        job_timeout = self.config.scheduler.job_timeout
        logger.info("=" * 50)
        logger.info(f"Starting news collection job (timeout={job_timeout}s)")
        start_time = datetime.now()

        # 设置 SIGALRM 超时保护（仅 Unix/macOS 支持）
        _job_timed_out = False
        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(job_timeout)
        except (AttributeError, ValueError):
            # Windows 或非主线程不支持 SIGALRM，跳过
            signal_available = False
        else:
            signal_available = True

        try:
            self._run_job_inner(start_time)
        except TimeoutError:
            logger.error(f"⚠️ Job timed out after {job_timeout}s, forcing termination!")
        except Exception as e:
            logger.error(f"Job failed with error: {e}")
        finally:
            # 取消 alarm
            if signal_available:
                signal.alarm(0)
            if _job_timed_out:
                logger.warning("Job was terminated due to timeout, next schedule will run normally")

    def _run_job_inner(self, start_time: datetime):
        """任务实际执行逻辑"""
        all_news: List[NewsItem] = []

        # 1. 执行所有爬虫（支持并发，带超时保护）
        max_workers = min(self.config.crawlers.max_concurrent, len(self.crawlers))
        crawler_timeout = self.config.crawlers.timeout + 30  # 爬虫超时 + 缓冲
        if max_workers > 1 and len(self.crawlers) > 1:
            logger.info(f"Starting concurrent crawling with {max_workers} workers")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有爬虫任务
                future_to_crawler = {
                    executor.submit(self._fetch_crawler, crawler): crawler
                    for crawler in self.crawlers
                }

                # 收集结果（带超时）
                for future in as_completed(future_to_crawler, timeout=crawler_timeout):
                    crawler = future_to_crawler[future]
                    try:
                        news_list = future.result(timeout=10)
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
                    notifier.send([], title=f"{notifier.default_title} - {datetime.now().strftime('%Y-%m-%d %H:%M')}", used_llm=False, custom_message="最近没有未推送的新闻了")
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
                notifier.send(
                    processed_news,
                    title=f"{notifier.default_title} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    used_llm=used_llm,
                )
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

    def _should_run_catchup(self) -> bool:
        """判断是否需要补偿执行：当前时间是否在某个 cron 时间点附近（±2小时）"""
        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute

        for cron_time in self.config.scheduler.cron_times:
            hour, minute = cron_time.split(":")
            cron_minutes = int(hour) * 60 + int(minute)
            # 如果当前时间在 cron 时间点的 2 小时内，说明可能错过了这次任务
            diff = abs(current_minutes - cron_minutes)
            if diff <= 120:  # 2小时窗口
                return True
        return False

    def start(self):
        """启动调度器"""
        # 添加定时任务
        for cron_time in self.config.scheduler.cron_times:
            hour, minute = cron_time.split(":")
            self.scheduler.add_job(
                self.run_job,
                trigger=CronTrigger(hour=int(hour), minute=int(minute)),
                name=f"NewsJob-{cron_time}",
                misfire_grace_time=7200,  # 错过任务宽限时间：2小时（覆盖休眠场景）
                coalesce=True,  # 合并错过的任务，只执行一次
                max_instances=1,  # 同时最多运行1个实例
            )
            logger.info(f"Scheduled job at {cron_time}")

        # 启动时检查是否需要补偿执行（处理休眠醒来后的场景）
        if self._should_run_catchup():
            logger.info("Startup catch-up: running missed job now")
            self.scheduler.add_job(
                self.run_job,
                name="CatchUpJob",
                misfire_grace_time=7200,
            )

        # 添加休眠检测心跳任务（每分钟检查一次）
        self.scheduler.add_job(
            self._sleep_check_job,
            trigger=CronTrigger(minute="*"),
            name="SleepCheckJob",
            misfire_grace_time=7200,
        )

        logger.info("Scheduler started. Press Ctrl+C to stop.")
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")

    def _sleep_check_job(self):
        """定期心跳，检测系统休眠恢复并触发补偿执行"""
        if _check_sleep_recovery():
            # 系统刚从休眠中恢复，检查是否需要补偿执行
            if self._should_run_catchup():
                logger.info("Sleep recovery: scheduling catch-up job")
                try:
                    # 避免重复添加，检查是否已有待执行的 job
                    existing_jobs = self.scheduler.get_jobs()
                    has_pending = any(
                        j.name in ("NewsJob-catchup", "CatchUpJob") and j.next_run_time
                        for j in existing_jobs
                    )
                    if not has_pending:
                        self.scheduler.add_job(
                            self.run_job,
                            name="NewsJob-catchup",
                            misfire_grace_time=7200,
                        )
                except Exception as e:
                    logger.error(f"Failed to schedule catch-up job: {e}")


def main():
    """主函数"""
    scheduler = NewsScheduler()
    scheduler.start()


if __name__ == "__main__":
    main()
