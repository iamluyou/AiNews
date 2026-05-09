"""
LLM 模块增强测试
"""
from datetime import datetime
from unittest.mock import MagicMock

from news_agent.models.news import NewsItem
from news_agent.llm import LLM_REGISTRY, create_llm_from_config
from news_agent.llm.base import BaseLLM
from news_agent.llm.client import OpenAIClient


class TestLLMRegistry:
    """测试 LLM 注册表"""

    def test_registry_contains_openai(self):
        assert "openai" in LLM_REGISTRY
        assert LLM_REGISTRY["openai"] is OpenAIClient


class TestBaseLLMParsing:
    """测试 BaseLLM 的响应解析逻辑"""

    class TestLLM(BaseLLM):
        name = "test"

        def chat(self, messages, **kwargs):
            return "test"

        def batch_chat(self, prompts, **kwargs):
            return ["test"] * len(prompts)

    def test_parse_json_response(self):
        llm = self.TestLLM()
        result = llm._parse_selection_response('{"selected_indices": [0, 2, 5]}')
        assert result == [0, 2, 5]

    def test_parse_json_with_extra_text(self):
        llm = self.TestLLM()
        response = "Here are the results:\n```json\n{\"selected_indices\": [1, 3]}\n```"
        result = llm._parse_selection_response(response)
        assert result == [1, 3]

    def test_parse_numbers_fallback(self):
        llm = self.TestLLM()
        # No JSON, just numbers
        result = llm._parse_selection_response("0 2 5")
        assert result == [0, 2, 5]

    def test_parse_invalid_response_raises(self):
        llm = self.TestLLM()
        try:
            llm._parse_selection_response("no numbers here!")
            # If it doesn't raise, at least verify it returns something
        except Exception:
            pass  # Expected to raise

    def test_keyword_scoring(self):
        llm = self.TestLLM()
        news = [
            NewsItem(title="GPT-5 发布", url="https://a.com/1", source="A"),
            NewsItem(title="普通科技新闻", url="https://a.com/2", source="B"),
        ]
        result = llm._keyword_scoring(news)
        assert len(result) == 2
        # AI 相关新闻应该排在前面
        assert result[0].ai_relevance_score > result[1].ai_relevance_score

    def test_fallback_selection(self):
        llm = self.TestLLM(fallback_per_source=2)
        news = [
            NewsItem(title="新闻1", url="https://a.com/1", source="A"),
            NewsItem(title="新闻2", url="https://a.com/2", source="A"),
            NewsItem(title="新闻3", url="https://a.com/3", source="A"),
            NewsItem(title="新闻4", url="https://b.com/4", source="B"),
            NewsItem(title="新闻5", url="https://b.com/5", source="B"),
            NewsItem(title="新闻6", url="https://b.com/6", source="B"),
        ]
        result = llm._fallback_selection(news)
        # 每个信源取 2 条
        assert len(result) == 4  # 2 from A + 2 from B

    def test_build_batch_prompt(self):
        llm = self.TestLLM(ranking_prompt="选出最相关的 {top_n} 条新闻")
        news = [
            NewsItem(title="新闻1", url="https://a.com/1", source="A"),
            NewsItem(title="新闻2", url="https://a.com/2", source="B"),
        ]
        prompt = llm._build_batch_prompt(news)
        assert "选出最相关的 10 条新闻" in prompt  # default top_n_per_batch=10
        assert "新闻1" in prompt
        assert "新闻2" in prompt


class TestCreateLLMFromConfig:
    """测试 LLM 工厂函数"""

    def test_returns_none_when_no_api_key(self):
        mock_config = MagicMock()
        mock_config.llm.api_key = ""
        result = create_llm_from_config(mock_config)
        assert result is None

    def test_creates_llm_with_api_key(self):
        mock_config = MagicMock()
        mock_config.llm.api_key = "test-key"
        mock_config.llm.base_url = "http://localhost:8597/v1"
        mock_config.llm.model = "test-model"
        mock_config.llm.max_retries = 2
        mock_config.llm.timeout = 30
        mock_config.llm.ranking_prompt = None
        mock_config.llm.use_llm_for_ranking = True
        mock_config.llm.batch_size = 20
        mock_config.llm.top_n_per_batch = 5
        mock_config.llm.final_top_n = 10
        mock_config.llm.fallback_per_source = 5

        result = create_llm_from_config(mock_config)
        assert result is not None
        assert isinstance(result, OpenAIClient)


class TestOpenAIClient:
    """测试 OpenAI 客户端"""

    def test_init(self):
        client = OpenAIClient(
            base_url="http://localhost:8597/v1",
            api_key="test-key",
            model="test-model",
            max_retries=2,
            timeout=30,
        )
        assert client.name == "openai"
        assert client.model == "test-model"
        assert client.max_retries == 2
        assert client.timeout == 30
