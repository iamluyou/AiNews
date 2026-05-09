#!/usr/bin/env python3
"""
一次性执行爬虫任务（不启动定时调度）
"""
import sys
from pathlib import Path

# 添加 src 到路径
src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from news_agent.config import get_config, set_config
from news_agent.crawlers import CRAWLER_REGISTRY
from news_agent.models.news import NewsItem
from news_agent.notifiers import FeishuNotifier, Email163Notifier
from news_agent.storage import init_db, NewsRepository
from news_agent.llm import OpenAIClient
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

    all_news = []

    # 执行爬虫
    crawler_config = config.crawlers
    for crawler_name in crawler_config.enabled:
        if crawler_name in CRAWLER_REGISTRY:
            logger.info(f"正在执行爬虫: {crawler_name}")
            try:
                crawler_cls = CRAWLER_REGISTRY[crawler_name]
                crawler = crawler_cls(
                    timeout=crawler_config.timeout,
                    request_delay=crawler_config.request_delay,
                )
                news_list = crawler.fetch()
                all_news.extend(news_list)
                logger.info(f"  抓取到 {len(news_list)} 条新闻")
            except Exception as e:
                logger.error(f"  爬虫 {crawler_name} 执行失败: {e}")

    if not all_news:
        logger.warning("没有抓取到任何新闻")
        return

    logger.info(f"共抓取到 {len(all_news)} 条新闻")

    # 内存去重（按 URL）
    seen_urls = set()
    unique_news = []
    for news in all_news:
        if news.url not in seen_urls:
            seen_urls.add(news.url)
            unique_news.append(news)
    logger.info(f"内存去重后剩余 {len(unique_news)} 条新闻")
    all_news = unique_news

    # 按发布时间排序
    all_news.sort(
        key=lambda x: x.publish_time or x.created_at,
        reverse=True
    )

    # 存储到数据库
    NewsRepository.add_batch(all_news)
    logger.info("新闻已存储到数据库")

    # 过滤掉已发送的新闻
    unsent_news = []
    for news in all_news:
        if not NewsRepository.is_sent(news.url):
            unsent_news.append(news)

    logger.info(f"共抓取到 {len(all_news)} 条新闻，其中 {len(unsent_news)} 条未发送")

    # 如果所有新闻都是已发送的，发送提示消息
    if not unsent_news:
        logger.info("所有新闻都是已发送过的，发送提示消息")
        # 发送飞书通知
        if config.feishu.enabled and config.feishu.webhook_urls:
            try:
                notifier = FeishuNotifier(config.feishu.webhook_urls)
                from datetime import datetime
                # 发送简单提示消息
                notifier.send([], title=f"新闻推送 - {datetime.now().strftime('%Y-%m-%d %H:%M')}", custom_message="最近没有未推送的新闻了")
                logger.info("飞书提示消息发送成功")
            except Exception as e:
                logger.error(f"飞书提示消息发送失败: {e}")
        # 发送邮件通知
        if config.email_163.enabled and config.email_163.sender:
            try:
                notifier = Email163Notifier(
                    sender=config.email_163.sender,
                    password=config.email_163.password,
                    recipients=config.email_163.recipients,
                )
                from datetime import datetime
                notifier.send([], title=f"AI 新闻整理 - {datetime.now().strftime('%Y-%m-%d %H:%M')}", used_llm=False, custom_message="最近没有未推送的新闻了")
                logger.info("邮件提示消息发送成功")
            except Exception as e:
                logger.error(f"邮件提示消息发送失败: {e}")
        logger.info("=" * 50)
        logger.info("任务执行完成")
        logger.info("=" * 50)
        return

    # 只处理未发送的新闻
    all_news = unsent_news

    # LLM 处理
    processed_news = all_news
    used_llm = False
    if config.llm.api_key:
        logger.info("正在使用 LLM 进行新闻智能筛选...")
        try:
            llm = OpenAIClient(
                base_url=config.llm.base_url,
                api_key=config.llm.api_key,
                model=config.llm.model,
                max_retries=config.llm.max_retries,
                timeout=config.llm.timeout,
                ranking_prompt=config.llm.ranking_prompt,
                use_llm_for_ranking=config.llm.use_llm_for_ranking,
                batch_size=config.llm.batch_size,
                top_n_per_batch=config.llm.top_n_per_batch,
                final_top_n=config.llm.final_top_n,
                fallback_per_source=config.llm.fallback_per_source,
            )
            # 如果启用了 LLM 评分，标记为已使用
            used_llm = config.llm.use_llm_for_ranking
            processed_news = llm.process_news(all_news)
            logger.info(f"LLM 处理完成，剩余 {len(processed_news)} 条新闻")
        except Exception as e:
            logger.error(f"LLM 处理失败: {e}")
            processed_news = all_news
            used_llm = False
    else:
        # 如果没有 LLM 配置，按发布时间排序
        processed_news.sort(
            key=lambda x: x.publish_time or x.created_at,
            reverse=True
        )

    # 发送所有候选新闻（不再截断 Top 20）
    top_news = processed_news
    logger.info(f"将发送 {len(top_news)} 条新闻")

    # 发送飞书通知（只发 Top 20）
    if config.feishu.enabled and config.feishu.webhook_urls:
        logger.info("正在发送飞书通知...")
        try:
            notifier = FeishuNotifier(config.feishu.webhook_urls)
            from datetime import datetime
            notifier.send(top_news, title=f"新闻推送 - {datetime.now().strftime('%Y-%m-%d %H:%M')}", used_llm=used_llm)
            logger.info("飞书通知发送成功")
        except Exception as e:
            logger.error(f"飞书通知发送失败: {e}")

    # 发送邮件通知（只发 Top 20）
    if config.email_163.enabled and config.email_163.sender:
        logger.info("正在发送邮件通知...")
        try:
            notifier = Email163Notifier(
                sender=config.email_163.sender,
                password=config.email_163.password,
                recipients=config.email_163.recipients,
            )
            from datetime import datetime
            notifier.send(top_news, title=f"AI 新闻整理 - {datetime.now().strftime('%Y-%m-%d %H:%M')}", used_llm=used_llm)
            logger.info("邮件通知发送成功")
        except Exception as e:
            logger.error(f"邮件通知发送失败: {e}")

    # 标记新闻为已发送
    if top_news:
        sent_urls = [news.url for news in top_news]
        NewsRepository.mark_as_sent(sent_urls)
        logger.info(f"已标记 {len(sent_urls)} 条新闻为已发送")

    logger.info("=" * 50)
    logger.info("任务执行完成")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_once()
