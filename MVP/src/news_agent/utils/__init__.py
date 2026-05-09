from .logger import get_logger
from .deduplication import deduplicate_news_by_url, deduplicate_by_field

__all__ = ["get_logger", "deduplicate_news_by_url", "deduplicate_by_field"]
