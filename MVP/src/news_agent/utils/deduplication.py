"""
去重工具函数
"""
from typing import List, Dict, Any
from collections import OrderedDict

from ..models.news import NewsItem
from ..utils.logger import get_logger

logger = get_logger(__name__)


def deduplicate_news_by_url(news_list: List[NewsItem]) -> List[NewsItem]:
    """
    按 URL 去重新闻列表，保留第一次出现的新闻

    Args:
        news_list: 新闻列表

    Returns:
        去重后的新闻列表
    """
    if not news_list:
        return []

    # 使用 OrderedDict 保持顺序
    unique_map = OrderedDict()

    for news in news_list:
        if news.url not in unique_map:
            unique_map[news.url] = news

    result = list(unique_map.values())
    removed_count = len(news_list) - len(result)

    if removed_count > 0:
        logger.debug(f"Deduplicated {removed_count} news by URL")

    return result


def deduplicate_by_field(items: List[Any], field_name: str) -> List[Any]:
    """
    按指定字段去重列表，保留第一次出现的项

    Args:
        items: 待去重的列表
        field_name: 用于去重的字段名

    Returns:
        去重后的列表
    """
    if not items:
        return []

    unique_map = OrderedDict()

    for item in items:
        field_value = getattr(item, field_name, None)
        if field_value is not None and field_value not in unique_map:
            unique_map[field_value] = item
        elif field_value is None:
            # 字段值为 None 的项也保留（不移除）
            pass

    return list(unique_map.values())
