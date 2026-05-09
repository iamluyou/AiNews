from typing import List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

from .base import BaseNotifier
from ..models.news import NewsItem
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Email163Notifier(BaseNotifier):
    """163 邮件通知"""

    name = "email_163"

    def __init__(self, sender: str, password: str, recipients: List[str], sender_name: str = "AI 新闻助手"):
        self.sender = sender
        self.sender_name = sender_name
        self.password = password
        self.recipients = recipients
        self.smtp_host = "smtp.163.com"
        self.smtp_port = 465

    def send(self, news_list: List[NewsItem], title: str = "AI 新闻整理", used_llm: bool = False, custom_message: str = None) -> bool:
        """发送邮件通知"""
        if not news_list and not custom_message:
            logger.warning("No news or message to send via email")
            return False

        if not self.recipients:
            logger.warning("No recipients configured")
            return False

        try:
            # 构建邮件内容
            if custom_message:
                html_content = self._build_custom_message_html(title, custom_message)
            else:
                html_content = self._build_html(news_list, title, used_llm)

            # 创建邮件
            msg = MIMEMultipart("alternative")
            # Format sender as "Name <email>"
            from_addr = f"{self.sender_name} <{self.sender}>"
            msg["From"] = Header(from_addr)
            msg["To"] = Header(", ".join(self.recipients))
            msg["Subject"] = Header(title, "utf-8")

            # 添加 HTML 内容
            html_part = MIMEText(html_content, "html", "utf-8")
            msg.attach(html_part)

            # 发送邮件
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                server.login(self.sender, self.password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {len(self.recipients)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _build_html(self, news_list: List[NewsItem], title: str, used_llm: bool) -> str:
        """构建 HTML 邮件内容"""
        llm_badge = ""
        if used_llm:
            llm_badge = '<span style="background: #4CAF50; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">🤖 AI 智能筛选</span>'
        else:
            llm_badge = '<span style="background: #FF9800; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">📋 关键词筛选</span>'

        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                h1 {{ color: #333; }}
                .header-meta {{ margin: 10px 0; }}
                .news-item {{ margin: 15px 0; padding: 10px; border-bottom: 1px solid #eee; }}
                .news-title {{ font-size: 16px; font-weight: bold; }}
                .news-title a {{ color: #1a73e8; text-decoration: none; }}
                .news-meta {{ color: #666; font-size: 12px; margin-top: 5px; }}
                .score {{ color: #e91e63; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            <div class="header-meta">{llm_badge}</div>
        """

        for news in news_list:
            score_html = ""
            if news.ai_relevance_score is not None:
                score_html = f' | <span class="score">AI 相关度: {news.ai_relevance_score:.2%}</span>'

            time_str = news.publish_time.strftime("%Y-%m-%d %H:%M") if news.publish_time else ""
            source_str = f"来源: {news.source}" if news.source else ""

            html += f"""
            <div class="news-item">
                <div class="news-title">
                    <a href="{news.url}" target="_blank">{news.title}</a>
                </div>
                <div class="news-meta">
                    {time_str} | {source_str}{score_html}
                </div>
            </div>
            """

        html += """
        </body>
        </html>
        """
        return html

    def _build_custom_message_html(self, title: str, message: str) -> str:
        """构建自定义提示消息的 HTML"""
        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                h1 {{ color: #333; }}
                .message {{
                    background: #f5f5f5;
                    padding: 20px;
                    border-radius: 8px;
                    margin-top: 20px;
                    font-size: 16px;
                    color: #666;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            <div class="message">
                {message}
            </div>
        </body>
        </html>
        """
        return html
