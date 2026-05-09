from abc import ABC, abstractmethod
from typing import List
import time

import requests
from bs4 import BeautifulSoup

from ..models.news import NewsItem
from ..utils.logger import get_logger

logger = get_logger(__name__)


class BaseCrawler(ABC):
    """爬虫基类"""

    # 子类必须定义这些属性
    name: str = ""
    base_url: str = ""
    source_name: str = ""

    def __init__(self, timeout: int = 30, request_delay: float = 2.0):
        self.timeout = timeout
        self.request_delay = request_delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        })

    @abstractmethod
    def fetch(self) -> List[NewsItem]:
        """执行爬取并返回新闻列表"""
        pass

    def _get(self, url: str, **kwargs) -> requests.Response:
        """发送 GET 请求（带重试机制）"""
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                time.sleep(self.request_delay)
                logger.debug(f"Fetching {url} (attempt {attempt + 1}/{max_retries})")
                response = self.session.get(url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    logger.warning(f"Request timed out, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Request timed out after {max_retries} attempts")
                    raise
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Request failed: {e}, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    raise

    def _parse_html(self, html: str) -> BeautifulSoup:
        """解析 HTML"""
        return BeautifulSoup(html, "lxml")

    def _create_news_item(
        self,
        title: str,
        url: str,
        cover_image: str = None,
        publish_time=None,
        content: str = None,
    ) -> NewsItem:
        """创建新闻项"""
        return NewsItem(
            title=title.strip(),
            url=url if url.startswith("http") else self.base_url.rstrip("/") + url,
            cover_image=cover_image,
            publish_time=publish_time,
            source=self.source_name,
            content=content,
        )
