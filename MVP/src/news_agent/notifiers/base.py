from abc import ABC, abstractmethod
from typing import List

from ..models.news import NewsItem
from ..utils.logger import get_logger

logger = get_logger(__name__)


class BaseNotifier(ABC):
    """通知基类"""

    name: str = ""

    @abstractmethod
    def send(self, news_list: List[NewsItem], title: str = "") -> bool:
        """发送通知"""
        pass

    def format_news_list(self, news_list: List[NewsItem]) -> str:
        """格式化新闻列表为文本"""
        lines = []
        for i, news in enumerate(news_list, 1):
            line = f"{i}. [{news.title}]({news.url})"
            if news.publish_time:
                line += f" - {news.publish_time.strftime('%Y-%m-%d %H:%M')}"
            lines.append(line)
        return "\n".join(lines)
