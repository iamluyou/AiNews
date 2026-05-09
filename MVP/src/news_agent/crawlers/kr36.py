from typing import List
from datetime import datetime
import json
import re

from .base import BaseCrawler
from ..models.news import NewsItem
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Kr36Crawler(BaseCrawler):
    """36氪爬虫"""

    name = "kr36"
    base_url = "https://www.36kr.com"
    source_name = "36氪"

    def fetch(self) -> List[NewsItem]:
        """爬取36氪新闻"""
        news_list = []
        try:
            url = "https://www.36kr.com/information/AI"
            response = self._get(url)
            html = response.text

            # 尝试从 window.initialState 中提取 JSON 数据
            data = self._extract_initial_state(html)

            if data and "information" in data and "informationList" in data["information"]:
                item_list = data["information"]["informationList"].get("itemList", [])
                logger.info(f"Found {len(item_list)} items from initialState")

                for item in item_list:
                    try:
                        item_data = item.get("templateMaterial", {})
                        title = item_data.get("widgetTitle", "")
                        item_id = item.get("itemId")

                        if not title or not item_id:
                            continue

                        # 构建链接
                        news_url = f"{self.base_url}/p/{item_id}"

                        # 尝试获取发布时间
                        publish_time = None
                        ts = item_data.get("publishTime")
                        if ts:
                            try:
                                publish_time = datetime.fromtimestamp(ts / 1000)
                            except Exception:
                                pass

                        news = self._create_news_item(
                            title=title,
                            url=news_url,
                            publish_time=publish_time,
                        )
                        news_list.append(news)

                    except Exception as e:
                        logger.warning(f"Failed to parse item: {e}")
                        continue

            else:
                # 如果没有找到 initialState，降级为普通链接提取
                logger.warning("Could not find initialState, falling back to link extraction")
                soup = self._parse_html(html)

                articles = []
                for a in soup.find_all("a", href=True):
                    href = a.get("href", "")
                    text = a.get_text(strip=True)
                    if text and len(text) > 8 and (href.startswith("/") or "36kr.com" in href):
                        articles.append({"text": text, "href": href})

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

        # 去重
        seen = set()
        unique_news = []
        for news in news_list:
            if news.url not in seen:
                seen.add(news.url)
                unique_news.append(news)

        logger.info(f"Fetched {len(unique_news)} news from {self.source_name}")
        return unique_news

    def _extract_initial_state(self, html: str) -> dict:
        """从 HTML 中提取 window.initialState 数据"""
        try:
            # 匹配 window.initialState = {...} 模式
            pattern = r'window\.initialState\s*=\s*({.*?});?\s*(?=</script>|$)'
            match = re.search(pattern, html, re.DOTALL)

            if match:
                json_str = match.group(1)
                # 清理一些可能的尾随字符
                json_str = json_str.rstrip(";")
                return json.loads(json_str)
        except Exception as e:
            logger.debug(f"Failed to extract initialState: {e}")

        return {}
