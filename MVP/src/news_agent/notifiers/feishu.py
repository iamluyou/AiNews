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

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

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

            response = requests.post(
                self.webhook_url,
                json=data,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            if result.get("code") == 0:
                logger.info(f"Feishu notification sent successfully")
                return True
            else:
                logger.error(f"Feishu notification failed: {result}")
                return False

        except Exception as e:
            logger.error(f"Failed to send feishu notification: {e}")
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
