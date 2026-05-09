from typing import List
from datetime import datetime

from .base import BaseCrawler
from ..models.news import NewsItem
from ..utils.logger import get_logger

logger = get_logger(__name__)


class QbitCrawler(BaseCrawler):
    """QbitAI爬虫"""

    name = "qbit"
    base_url = "https://www.qbitai.com"
    source_name = "QbitAI"

    def fetch(self) -> List[NewsItem]:
        """爬取QbitAI新闻"""
        news_list = []
        try:
            url = self.base_url
            response = self._get(url)
            soup = self._parse_html(response.text)

            articles = []
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if text and len(text) > 8 and (href.startswith("/") or "qbitai.com" in href):
                    articles.append({"elem": a, "text": text, "href": href})

            logger.debug(f"Found {len(articles)} potential articles")

            for item in articles[:30]:
                try:
                    title = item["text"]
                    url = item["href"]
                    if not url or not title:
                        continue
                    news = self._create_news_item(
                        title=title,
                        url=url,
                        publish_time=datetime.now(),
                    )
                    news_list.append(news)
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Failed to fetch from {self.source_name}: {e}")

        seen = set()
        unique_news = []
        for news in news_list:
            if news.url not in seen:
                seen.add(news.url)
                unique_news.append(news)

        logger.info(f"Fetched {len(unique_news)} news from {self.source_name}")
        return unique_news
