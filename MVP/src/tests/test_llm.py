"""
大模型模块测试
"""
from datetime import datetime

from news_agent.llm.base import BaseLLM
from news_agent.models.news import NewsItem


class MockLLM(BaseLLM):
    """模拟 LLM 用于测试"""

    name = "mock"

    def chat(self, messages, **kwargs):
        return "Mock response"

    def batch_chat(self, prompts, **kwargs):
        return ["Mock response"] * len(prompts)


class TestBaseLLM:
    """测试 LLM 基类"""

    def test_process_news_deduplication(self):
        """测试新闻去重"""
        llm = MockLLM()

        news1 = NewsItem(
            title="新闻1",
            url="https://example.com/1",
            source="测试",
            created_at=datetime(2024, 1, 1),
        )
        news2 = NewsItem(
            title="新闻2",
            url="https://example.com/2",
            source="测试",
            created_at=datetime(2024, 1, 1),
        )
        news1_dup = NewsItem(
            title="新闻1重复",
            url="https://example.com/1",
            source="测试",
            created_at=datetime(2024, 1, 2),
        )

        result = llm.process_news([news1, news2, news1_dup])
        assert len(result) == 2

    def test_process_news_scoring(self):
        """测试新闻评分"""
        llm = MockLLM()

        news1 = NewsItem(
            title="AI 大模型最新进展",
            url="https://example.com/1",
            source="测试",
        )
        news2 = NewsItem(
            title="普通新闻标题",
            url="https://example.com/2",
            source="测试",
        )

        result = llm.process_news([news1, news2])
        assert len(result) == 2
        # AI 相关的新闻应该有更高的分数
        assert result[0].ai_relevance_score is not None
        assert result[1].ai_relevance_score is not None
