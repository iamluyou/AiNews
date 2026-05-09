from typing import List
from datetime import datetime
import json

from .base import BaseCrawler
from ..models.news import NewsItem
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RadarCrawler(BaseCrawler):
    """RadarAI爬虫"""

    name = "radar"
    base_url = "https://radarai.top"
    source_name = "RadarAI"

    def fetch(self) -> List[NewsItem]:
        """爬取RadarAI新闻"""
        news_list = []
        try:
            url = self.base_url
            response = self._get(url)
            html = response.text

            # 方法1: 从 SSR 内容的 article-card 中提取（优先）
            news_list = self._extract_from_ssr(html)

            if not news_list:
                # 方法2: 从 JSON-LD 中提取（备选）
                news_list = self._extract_from_json_ld(html)

            if not news_list:
                # 方法3: 降级为普通链接提取
                logger.warning("Falling back to basic link extraction")
                news_list = self._extract_basic_links(html)

        except Exception as e:
            logger.error(f"Failed to fetch from {self.source_name}: {e}")

        # 去重
        seen = set()
        unique_news = []
        for news in news_list:
            if news.url not in seen:
                seen.add(news.url)
                unique_news.append(news)

        logger.info(f"Fetched {len(unique_news)} news from {self.source_name}")
        return unique_news

    def _extract_from_ssr(self, html: str) -> List[NewsItem]:
        """从 SSR 内容的 article-card 中提取新闻"""
        news_list = []
        try:
            soup = self._parse_html(html)
            ssr_div = soup.find("div", id="ssr-article-list")
            if not ssr_div:
                return []

            articles = ssr_div.find_all("article", class_="article-card")
            logger.info(f"Found {len(articles)} article-cards from SSR")

            for article in articles:
                try:
                    # 优先从 bookmark-btn 获取数据
                    bookmark_btn = article.find("button", class_="bookmark-btn")
                    if bookmark_btn:
                        title = bookmark_btn.get("data-title", "")
                        news_url = bookmark_btn.get("data-link", "")
                    else:
                        title = ""
                        news_url = ""

                    # 如果 bookmark-btn 没有数据，尝试从 a 标签获取
                    if not title or not news_url:
                        for a in article.find_all("a", href=True):
                            href = a.get("href", "")
                            text = a.get_text(strip=True)
                            if href and "bestblogs.dev/article/" in href:
                                news_url = href
                                if text and len(text) > 10:
                                    # 提取标题（去掉摘要部分）
                                    if "\n" in text:
                                        title = text.split("\n")[0].strip()
                                    else:
                                        title = text
                                break

                    if not title or not news_url:
                        continue

                    # 尝试获取发布时间
                    publish_time = None

                    news = self._create_news_item(
                        title=title,
                        url=news_url,
                        publish_time=publish_time,
                    )
                    news_list.append(news)

                except Exception as e:
                    logger.debug(f"Failed to parse article-card: {e}")
                    continue

        except Exception as e:
            logger.debug(f"Failed to extract from SSR: {e}")

        return news_list

    def _extract_from_json_ld(self, html: str) -> List[NewsItem]:
        """从 JSON-LD 结构化数据中提取新闻"""
        news_list = []
        try:
            soup = self._parse_html(html)
            scripts = soup.find_all("script", type="application/ld+json")

            for script in scripts:
                if not script.string:
                    continue
                try:
                    data = json.loads(script.string)
                    if data.get("@type") == "ItemList":
                        item_list = data.get("itemListElement", [])
                        logger.info(f"Found {len(item_list)} items from JSON-LD")

                        for item in item_list:
                            try:
                                article = item.get("item", {})
                                title = article.get("headline", "")
                                news_url = article.get("url", "")

                                if not title or not news_url:
                                    continue

                                # 尝试解析发布时间
                                publish_time = None
                                date_str = article.get("datePublished")
                                if date_str:
                                    try:
                                        # ISO 格式: 2026-04-15T13:51:00
                                        publish_time = datetime.fromisoformat(date_str)
                                    except Exception:
                                        pass

                                news = self._create_news_item(
                                    title=title,
                                    url=news_url,
                                    publish_time=publish_time,
                                )
                                news_list.append(news)

                            except Exception:
                                continue
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Failed to extract from JSON-LD: {e}")

        return news_list

    def _extract_basic_links(self, html: str) -> List[NewsItem]:
        """降级方案：提取所有链接"""
        news_list = []
        soup = self._parse_html(html)

        articles = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            # 只保留 bestblogs.dev 的文章链接
            if text and len(text) > 10 and "bestblogs.dev/article/" in href:
                articles.append({"text": text, "href": href})

        logger.debug(f"Found {len(articles)} potential articles (basic)")

        for item in articles[:80]:
            try:
                title = item["text"]
                # 提取标题（去掉摘要部分）
                if "\n" in title:
                    title = title.split("\n")[0].strip()
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

        return news_list
