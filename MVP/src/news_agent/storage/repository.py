from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import desc, and_

from ..models.news import NewsItem
from ..utils.logger import get_logger
from .database import session_scope, NewsModel

logger = get_logger(__name__)


class NewsRepository:
    """新闻数据仓库"""

    @staticmethod
    def add(news: NewsItem) -> bool:
        """添加新闻，已存在则更新（按 URL 去重）"""
        try:
            with session_scope() as session:
                existing = session.query(NewsModel).filter_by(url=news.url).first()
                if existing:
                    # 更新已存在的记录（但不更新 sent_at）
                    existing.title = news.title
                    existing.cover_image = news.cover_image
                    existing.publish_time = news.publish_time
                    existing.source = news.source
                    existing.content = news.content
                    existing.ai_relevance_score = news.ai_relevance_score
                    logger.debug(f"[DUPLICATE] Updated existing news: {news.title[:50]}...")
                    return False  # 返回 False 表示是重复的
                else:
                    # 创建新记录
                    model = NewsModel(
                        url=news.url,
                        title=news.title,
                        cover_image=news.cover_image,
                        publish_time=news.publish_time,
                        source=news.source,
                        content=news.content,
                        ai_relevance_score=news.ai_relevance_score,
                        created_at=news.created_at,
                        sent_at=news.sent_at,
                    )
                    session.add(model)
                    logger.debug(f"[NEW] Added news: {news.title[:50]}...")
                    return True  # 返回 True 表示是新增的
        except Exception as e:
            logger.error(f"Failed to add news: {e}")
            return False

    @staticmethod
    def add_batch(news_list: List[NewsItem]) -> int:
        """批量添加新闻，自动按 URL 去重（优化版：单 session 批量操作）"""
        if not news_list:
            return 0

        added_count = 0
        duplicate_count = 0

        try:
            with session_scope() as session:
                # 第一步：查询已存在的 URL
                urls = [news.url for news in news_list]
                existing_models = session.query(NewsModel).filter(NewsModel.url.in_(urls)).all()
                existing_urls = {model.url: model for model in existing_models}

                # 第二步：分别处理更新和新增
                news_to_create = []

                for news in news_list:
                    if news.url in existing_urls:
                        # 更新已存在的记录
                        existing = existing_urls[news.url]
                        existing.title = news.title
                        existing.cover_image = news.cover_image
                        existing.publish_time = news.publish_time
                        existing.source = news.source
                        existing.content = news.content
                        existing.ai_relevance_score = news.ai_relevance_score
                        duplicate_count += 1
                    else:
                        # 准备新增记录
                        model = NewsModel(
                            url=news.url,
                            title=news.title,
                            cover_image=news.cover_image,
                            publish_time=news.publish_time,
                            source=news.source,
                            content=news.content,
                            ai_relevance_score=news.ai_relevance_score,
                            created_at=news.created_at,
                            sent_at=news.sent_at,
                        )
                        news_to_create.append(model)
                        added_count += 1

                # 批量新增
                if news_to_create:
                    session.bulk_save_objects(news_to_create)

            logger.info(f"Batch complete: 新增 {added_count} 条, 跳过重复 {duplicate_count} 条, 总计 {len(news_list)} 条")
            return added_count

        except Exception as e:
            logger.error(f"Failed to add batch news: {e}")
            # 降级到单条处理
            logger.warning("Falling back to single news processing")
            added_count = 0
            for news in news_list:
                if NewsRepository.add(news):
                    added_count += 1
            return added_count

    @staticmethod
    def get_by_url(url: str) -> Optional[NewsItem]:
        """根据 URL 获取新闻"""
        with session_scope() as session:
            model = session.query(NewsModel).filter_by(url=url).first()
            if model:
                return NewsRepository._to_item(model)
            return None

    @staticmethod
    def get_by_source(source: str, limit: int = 100) -> List[NewsItem]:
        """根据来源获取新闻"""
        with session_scope() as session:
            models = (
                session.query(NewsModel)
                .filter_by(source=source)
                .order_by(desc(NewsModel.publish_time))
                .limit(limit)
                .all()
            )
            return [NewsRepository._to_item(m) for m in models]

    @staticmethod
    def get_by_time_range(
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> List[NewsItem]:
        """获取时间范围内的新闻"""
        with session_scope() as session:
            models = (
                session.query(NewsModel)
                .filter(
                    and_(
                        NewsModel.publish_time >= start_time,
                        NewsModel.publish_time <= end_time,
                    )
                )
                .order_by(desc(NewsModel.publish_time))
                .limit(limit)
                .all()
            )
            return [NewsRepository._to_item(m) for m in models]

    @staticmethod
    def get_latest(limit: int = 100) -> List[NewsItem]:
        """获取最新新闻"""
        with session_scope() as session:
            models = (
                session.query(NewsModel)
                .order_by(desc(NewsModel.created_at))
                .limit(limit)
                .all()
            )
            return [NewsRepository._to_item(m) for m in models]

    @staticmethod
    def exists(url: str) -> bool:
        """检查新闻是否已存在"""
        with session_scope() as session:
            return session.query(NewsModel).filter_by(url=url).first() is not None

    @staticmethod
    def mark_as_sent(urls: List[str]) -> int:
        """标记新闻为已发送（优化版：批量更新）"""
        if not urls:
            return 0

        from datetime import datetime
        now = datetime.now()
        count = 0

        try:
            with session_scope() as session:
                # 批量更新
                result = session.query(NewsModel).filter(
                    NewsModel.url.in_(urls)
                ).update(
                    {NewsModel.sent_at: now},
                    synchronize_session=False
                )
                count = result

            logger.info(f"Marked {count} news as sent")
            return count

        except Exception as e:
            logger.error(f"Failed to mark news as sent in batch: {e}")
            # 降级到逐条处理
            logger.warning("Falling back to single url processing")
            count = 0
            try:
                with session_scope() as session:
                    for url in urls:
                        model = session.query(NewsModel).filter_by(url=url).first()
                        if model:
                            model.sent_at = now
                            count += 1
                logger.info(f"Marked {count} news as sent (fallback)")
                return count
            except Exception as e2:
                logger.error(f"Failed to mark news as sent (fallback): {e2}")
                return 0

    @staticmethod
    def get_unsent(limit: int = 1000) -> List[NewsItem]:
        """获取未发送的新闻"""
        with session_scope() as session:
            models = (
                session.query(NewsModel)
                .filter(NewsModel.sent_at.is_(None))
                .order_by(desc(NewsModel.publish_time))
                .limit(limit)
                .all()
            )
            return [NewsRepository._to_item(m) for m in models]

    @staticmethod
    def is_sent(url: str) -> bool:
        """检查新闻是否已发送"""
        with session_scope() as session:
            model = session.query(NewsModel).filter_by(url=url).first()
            return model is not None and model.sent_at is not None

    @staticmethod
    def _to_item(model: NewsModel) -> NewsItem:
        """转换数据库模型为数据模型"""
        return NewsItem(
            title=model.title,
            url=model.url,
            cover_image=model.cover_image,
            publish_time=model.publish_time,
            source=model.source,
            content=model.content,
            ai_relevance_score=model.ai_relevance_score,
            created_at=model.created_at,
            sent_at=model.sent_at,
        )
