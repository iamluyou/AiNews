import time
from typing import List
import json

import requests

from .base import BaseNotifier
from ..models.news import NewsItem
from ..utils.logger import get_logger

logger = get_logger(__name__)


class FeishuNotifier(BaseNotifier):
    """飞书 Webhook 通知"""

    name = "feishu"

    # 飞书频率限制错误码
    FREQUENCY_LIMIT_CODES = {11232, 11233}

    def __init__(self, webhook_urls: List[str]):
        if isinstance(webhook_urls, str):
            webhook_urls = [webhook_urls]
        self.webhook_urls = webhook_urls

    def send(self, news_list: List[NewsItem], title: str = "新闻推送", used_llm: bool = False, custom_message: str = None) -> bool:
        """发送飞书通知"""
        if not news_list and not custom_message:
            logger.warning("No news or message to send to feishu")
            return False

        try:
            if custom_message:
                # 发送自定义消息
                content = f"📢 {title}\n\n{custom_message}"
            else:
                # 先用简单的 text 格式确保能工作
                content = self._build_text_message(news_list, title, used_llm)

            data = {
                "msg_type": "text",
                "content": {
                    "text": content
                }
            }

            success_count = 0
            for url in self.webhook_urls:
                if self._send_with_retry(url, data):
                    success_count += 1

            if success_count == len(self.webhook_urls):
                logger.info(f"Feishu notification sent successfully to all {success_count} webhooks")
                return True
            elif success_count > 0:
                logger.warning(f"Feishu notification sent to {success_count}/{len(self.webhook_urls)} webhooks")
                return False
            else:
                logger.error("Feishu notification failed for all webhooks")
                return False

        except Exception as e:
            logger.error(f"Failed to send feishu notification: {e}")
            return False

    def _send_with_retry(self, url: str, data: dict, max_retries: int = 2) -> bool:
        """发送请求，频率限制时自动重试"""
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(url, json=data, timeout=30)
                response.raise_for_status()

                result = response.json()
                if result.get("code") == 0:
                    return True

                # 频率限制，等待后重试
                if result.get("code") in self.FREQUENCY_LIMIT_CODES and attempt < max_retries:
                    wait = 5 * (attempt + 1)
                    logger.warning(f"Feishu rate limited for {url}, retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                    continue

                logger.error(f"Feishu notification failed for {url}: {result}")
                return False
            except Exception as e:
                logger.error(f"Failed to send feishu notification to {url}: {e}")
                return False
        return False

    def _build_text_message(self, news_list: List[NewsItem], title: str, used_llm: bool) -> str:
        """构建简单文本消息格式 - 显示所有新闻"""
        lines = [f"📢 {title}"]

        # Add LLM/badge
        if used_llm:
            lines.append("🤖 AI 智能筛选")
        else:
            lines.append("📋 关键词筛选")
        lines.append("")

        for i, news in enumerate(news_list, 1):
            time_str = news.publish_time.strftime("%Y-%m-%d %H:%M") if news.publish_time else ""
            line = f"{i}. {news.title}"
            if time_str:
                line += f" ({time_str})"
            line += f"\n   {news.url}"
            lines.append(line)

        return "\n".join(lines)
