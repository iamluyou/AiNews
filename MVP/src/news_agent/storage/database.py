from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, Column, String, DateTime, Text, Float
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from ..config import get_config
from ..utils.logger import get_logger

logger = get_logger(__name__)

Base = declarative_base()


class NewsModel(Base):
    """新闻数据库模型"""
    __tablename__ = "news"

    url = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    cover_image = Column(String, nullable=True)
    publish_time = Column(DateTime, nullable=True, index=True)
    source = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=True)
    ai_relevance_score = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True, index=True)


_engine = None
_session_factory = None


def init_db(db_path: Optional[str] = None) -> None:
    """初始化数据库"""
    global _engine, _session_factory

    if db_path is None:
        config = get_config()
        db_path = config.database.path

    # 确保目录存在
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # 创建引擎
    db_url = f"sqlite:///{db_path}"
    _engine = create_engine(db_url, echo=False)
    _session_factory = sessionmaker(bind=_engine)

    # 创建表
    Base.metadata.create_all(_engine)

    # 数据库迁移：添加 sent_at 列（如果不存在）
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(_engine)
        columns = [col['name'] for col in inspector.get_columns('news')]
        if 'sent_at' not in columns:
            logger.info("Migrating database: adding sent_at column")
            with _engine.connect() as conn:
                conn.execute(text("ALTER TABLE news ADD COLUMN sent_at DATETIME"))
                conn.commit()
            logger.info("Database migration completed")
    except Exception as e:
        logger.warning(f"Database migration check skipped: {e}")

    logger.info(f"Database initialized at {db_path}")


def get_session() -> Session:
    """获取数据库会话"""
    if _session_factory is None:
        init_db()
    return _session_factory()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """会话上下文管理"""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
