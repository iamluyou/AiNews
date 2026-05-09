"""
调度器增强测试（休眠检测、补偿逻辑、超时保护）
"""
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from news_agent.scheduler import (
    _check_sleep_recovery,
    _last_heartbeat,
)
from news_agent.models.news import NewsItem
from news_agent.pipeline import (
    create_crawlers,
    fetch_all_news,
    process_and_notify,
)


class TestSleepDetection:
    """测试休眠检测"""

    def test_no_sleep_detected(self):
        """正常心跳不应检测到休眠"""
        # 重置心跳时间
        import news_agent.scheduler as sched
        sched._last_heartbeat = time.time()
        result = _check_sleep_recovery()
        assert result is False

    def test_sleep_detected_after_large_gap(self):
        """大时间差应检测到休眠"""
        import news_agent.scheduler as sched
        # 模拟上次心跳是 300 秒前
        sched._last_heartbeat = time.time() - 300
        result = _check_sleep_recovery(sleep_threshold=120)
        assert result is True

    def test_no_sleep_within_threshold(self):
        """在阈值内不应检测到休眠"""
        import news_agent.scheduler as sched
        # 模拟上次心跳是 60 秒前
        sched._last_heartbeat = time.time() - 60
        result = _check_sleep_recovery(sleep_threshold=120)
        assert result is False

    def test_heartbeat_resets_after_detection(self):
        """检测到休眠后应重置心跳时间"""
        import news_agent.scheduler as sched
        sched._last_heartbeat = time.time() - 300
        _check_sleep_recovery(sleep_threshold=120)
        # 再次检查不应检测到休眠
        result = _check_sleep_recovery(sleep_threshold=120)
        assert result is False


class TestCatchupLogic:
    """测试补偿执行逻辑"""

    @patch("news_agent.scheduler.get_config")
    @patch("news_agent.scheduler.setup_logger")
    @patch("news_agent.scheduler.init_db")
    def test_should_run_catchup_near_cron_time(self, mock_db, mock_log, mock_config):
        """当前时间在 cron 时间附近应触发补偿"""
        from news_agent.scheduler import NewsScheduler

        mock_cfg = Mock()
        mock_cfg.scheduler.cron_times = ["09:30", "17:30"]
        mock_cfg.scheduler.timezone = "Asia/Shanghai"
        mock_cfg.scheduler.job_timeout = 300
        mock_cfg.crawlers.enabled = []
        mock_cfg.crawlers.timeout = 30
        mock_cfg.crawlers.request_delay = 0.1
        mock_cfg.llm.api_key = ""
        mock_cfg.feishu.enabled = False
        mock_cfg.feishu.webhook_urls = []
        mock_cfg.email_163.enabled = False
        mock_cfg.email_163.sender = ""
        mock_cfg.logging.file_path = "/tmp/test.log"
        mock_cfg.logging.level = "INFO"
        mock_config.return_value = mock_cfg

        scheduler = NewsScheduler.__new__(NewsScheduler)
        scheduler.config = mock_cfg

        # 用一个固定的 cron 时间测试
        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute

        # 构造一个在当前时间 30 分钟内的 cron 时间
        cron_hour = now.hour
        cron_minute = max(0, now.minute - 30)
        mock_cfg.scheduler.cron_times = [f"{cron_hour:02d}:{cron_minute:02d}"]

        result = scheduler._should_run_catchup()
        # 当前时间与 cron 时间差 30 分钟，在 2 小时窗口内
        assert result is True

    @patch("news_agent.scheduler.get_config")
    @patch("news_agent.scheduler.setup_logger")
    @patch("news_agent.scheduler.init_db")
    def test_should_not_catchup_far_from_cron(self, mock_db, mock_log, mock_config):
        """当前时间远离所有 cron 时间不应触发补偿"""
        from news_agent.scheduler import NewsScheduler

        mock_cfg = Mock()
        # 设置一个不太可能匹配的时间（凌晨 3:00）
        mock_cfg.scheduler.cron_times = ["03:00"]
        mock_scheduler_timezone = "Asia/Shanghai"

        scheduler = NewsScheduler.__new__(NewsScheduler)
        scheduler.config = mock_cfg

        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute
        cron_minutes = 3 * 60  # 03:00
        diff = abs(current_minutes - cron_minutes)

        # 只有当差值大于 120 分钟时才测试
        if diff > 120:
            result = scheduler._should_run_catchup()
            assert result is False


class TestRunJobTimeout:
    """测试任务超时保护"""

    @patch("news_agent.scheduler.get_config")
    @patch("news_agent.scheduler.setup_logger")
    @patch("news_agent.scheduler.init_db")
    def test_run_job_catches_exception(self, mock_db, mock_log, mock_config):
        """run_job 应捕获所有异常不影响调度器"""
        from news_agent.scheduler import NewsScheduler

        mock_cfg = Mock()
        mock_cfg.scheduler.job_timeout = 300
        mock_cfg.scheduler.timezone = "Asia/Shanghai"
        mock_cfg.crawlers.enabled = []
        mock_cfg.crawlers.timeout = 30
        mock_cfg.crawlers.request_delay = 0.1
        mock_cfg.llm.api_key = ""
        mock_cfg.feishu.enabled = False
        mock_cfg.feishu.webhook_urls = []
        mock_cfg.email_163.enabled = False
        mock_cfg.email_163.sender = ""
        mock_cfg.logging.file_path = "/tmp/test.log"
        mock_cfg.logging.level = "INFO"
        mock_config.return_value = mock_cfg

        scheduler = NewsScheduler.__new__(NewsScheduler)
        scheduler.config = mock_cfg

        # 模拟 _run_job_inner 抛出异常
        with patch.object(scheduler, '_run_job_inner', side_effect=Exception("test error")):
            # 不应抛出异常
            scheduler.run_job()


class TestSchedulerInitWithFactories:
    """测试 scheduler 使用工厂函数初始化"""

    @patch("news_agent.scheduler.create_notifiers_from_config")
    @patch("news_agent.scheduler.create_llm_from_config")
    @patch("news_agent.scheduler.create_crawlers")
    @patch("news_agent.scheduler.get_config")
    @patch("news_agent.scheduler.setup_logger")
    @patch("news_agent.scheduler.init_db")
    def test_uses_notifier_factory(self, mock_db, mock_log, mock_config, mock_crawlers_factory, mock_llm_factory, mock_notifier_factory):
        """验证 scheduler 使用工厂函数创建通知器"""
        from news_agent.scheduler import NewsScheduler

        mock_cfg = Mock()
        mock_cfg.scheduler.timezone = "Asia/Shanghai"
        mock_cfg.logging.file_path = "/tmp/test.log"
        mock_cfg.logging.level = "INFO"
        mock_config.return_value = mock_cfg

        mock_notifier = Mock()
        mock_notifier.name = "test_notifier"
        mock_notifier_factory.return_value = [mock_notifier]
        mock_llm_factory.return_value = None
        mock_crawlers_factory.return_value = []

        scheduler = NewsScheduler()
        mock_notifier_factory.assert_called_once_with(mock_cfg)
        assert len(scheduler.notifiers) == 1

    @patch("news_agent.scheduler.create_notifiers_from_config")
    @patch("news_agent.scheduler.create_llm_from_config")
    @patch("news_agent.scheduler.create_crawlers")
    @patch("news_agent.scheduler.get_config")
    @patch("news_agent.scheduler.setup_logger")
    @patch("news_agent.scheduler.init_db")
    def test_uses_llm_factory(self, mock_db, mock_log, mock_config, mock_crawlers_factory, mock_llm_factory, mock_notifier_factory):
        """验证 scheduler 使用工厂函数创建 LLM"""
        from news_agent.scheduler import NewsScheduler

        mock_cfg = Mock()
        mock_cfg.scheduler.timezone = "Asia/Shanghai"
        mock_cfg.logging.file_path = "/tmp/test.log"
        mock_cfg.logging.level = "INFO"
        mock_config.return_value = mock_cfg

        mock_llm = Mock()
        mock_llm_factory.return_value = mock_llm
        mock_notifier_factory.return_value = []
        mock_crawlers_factory.return_value = []

        scheduler = NewsScheduler()
        mock_llm_factory.assert_called_once_with(mock_cfg)
        assert scheduler.llm is mock_llm
