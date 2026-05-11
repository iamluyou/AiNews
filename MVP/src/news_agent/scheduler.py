"""新闻调度器：负责定时调度、超时保护、休眠检测"""

from datetime import datetime
from typing import List, Optional
import signal
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_config
from .crawlers import BaseCrawler
from .llm import create_llm_from_config, BaseLLM
from .notifiers import create_notifiers_from_config, BaseNotifier
from .pipeline import create_crawlers, fetch_all_news, process_and_notify
from .storage import init_db
from .utils.logger import get_logger, setup_logger

logger = get_logger(__name__)

# 全局超时标志
_job_timed_out = False

# 休眠检测：记录上次心跳时间
_last_heartbeat = time.time()


def _timeout_handler(signum, frame):
    """SIGALRM 信号处理器"""
    global _job_timed_out
    _job_timed_out = True
    raise TimeoutError("Job execution timed out")


def _check_sleep_recovery(sleep_threshold: int = 120):
    """检测系统从休眠中恢复

    Args:
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
        """初始化组件（通过工厂函数）"""
        self.crawlers = create_crawlers(self.config)
        self.notifiers = create_notifiers_from_config(self.config)
        self.llm = create_llm_from_config(self.config)

    def run_job(self):
        """执行一次完整任务（带超时保护）"""
        global _job_timed_out

        job_timeout = self.config.scheduler.job_timeout
        logger.info("=" * 50)
        logger.info(f"Starting news collection job (timeout={job_timeout}s)")
        start_time = datetime.now()

        # 设置 SIGALRM 超时保护（仅 Unix/macOS 支持）
        _job_timed_out = False
        signal_available = False
        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(job_timeout)
            signal_available = True
        except (AttributeError, ValueError):
            pass

        try:
            self._run_job_inner(start_time)
        except TimeoutError:
            logger.error(f"⚠️ Job timed out after {job_timeout}s, forcing termination!")
        except Exception as e:
            logger.error(f"Job failed with error: {e}")
        finally:
            if signal_available:
                signal.alarm(0)
            if _job_timed_out:
                logger.warning("Job was terminated due to timeout, next schedule will run normally")

    def _run_job_inner(self, start_time: datetime):
        """任务执行逻辑：委托给 pipeline"""
        # 1. 抓取
        crawler_timeout = self.config.crawlers.timeout + 30
        all_news = fetch_all_news(
            self.crawlers,
            max_concurrent=self.config.crawlers.max_concurrent,
            timeout=crawler_timeout,
        )

        # 2. 处理与通知
        process_and_notify(all_news, self.notifiers, self.llm)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Job completed in {duration:.2f} seconds")
        logger.info("=" * 50)

    def _should_run_catchup(self) -> bool:
        """判断是否需要补偿执行：当前时间距最近的 cron 时间点超过阈值（即错过了）"""
        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute

        for cron_time in self.config.scheduler.cron_times:
            hour, minute = cron_time.split(":")
            cron_minutes = int(hour) * 60 + int(minute)
            # 只检查已过去的 cron 时间点（当前时间已超过 cron 时间）
            # 如果距下一个 cron 时间很近（≤30分钟），说明 cron job 即将触发，不需要 catchup
            diff = current_minutes - cron_minutes
            if 30 < diff <= 120:
                return True
        return False

    def start(self):
        """启动调度器"""
        for cron_time in self.config.scheduler.cron_times:
            hour, minute = cron_time.split(":")
            self.scheduler.add_job(
                self.run_job,
                trigger=CronTrigger(hour=int(hour), minute=int(minute)),
                name=f"NewsJob-{cron_time}",
                misfire_grace_time=7200,
                coalesce=True,
                max_instances=1,
            )
            logger.info(f"Scheduled job at {cron_time}")

        # 启动时补偿执行（仅当距下一个 cron 时间较远时才补偿）
        if self._should_run_catchup():
            logger.info("Startup catch-up: running missed job now")
            self.run_job()

        # 休眠检测心跳
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
            if self._should_run_catchup():
                logger.info("Sleep recovery: scheduling catch-up job")
                self.run_job()


def main():
    """主函数"""
    scheduler = NewsScheduler()
    scheduler.start()


if __name__ == "__main__":
    main()
