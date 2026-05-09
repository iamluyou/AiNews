from abc import ABC, abstractmethod
from typing import List, Optional
import json
import re

from ..models.news import NewsItem
from ..utils.logger import get_logger
from ..utils import deduplicate_news_by_url

logger = get_logger(__name__)


class BaseLLM(ABC):
    """大模型基类"""

    name: str = ""

    def __init__(
        self,
        ranking_prompt: Optional[str] = None,
        use_llm_for_ranking: bool = True,
        batch_size: int = 30,
        top_n_per_batch: int = 10,
        final_top_n: int = 20,
        fallback_per_source: int = 10,
    ):
        self.ranking_prompt = ranking_prompt
        self.use_llm_for_ranking = use_llm_for_ranking
        self.batch_size = batch_size
        self.top_n_per_batch = top_n_per_batch
        self.final_top_n = final_top_n
        self.fallback_per_source = fallback_per_source

    @abstractmethod
    def chat(self, messages: List[dict], **kwargs) -> Optional[str]:
        """对话接口"""
        pass

    @abstractmethod
    def batch_chat(self, prompts: List[str], **kwargs) -> List[Optional[str]]:
        """批量对话接口"""
        pass

    def process_news(
        self,
        news_list: List[NewsItem],
    ) -> List[NewsItem]:
        """处理新闻：排序、去重、评分"""
        if not news_list:
            return []

        # 去重（基于 URL）
        news_list = deduplicate_news_by_url(news_list)
        logger.info(f"After deduplication: {len(news_list)} news")

        # 使用 LLM 进行筛选和排序，或使用降级方案
        if self.use_llm_for_ranking:
            try:
                news_list = self._rank_news_with_llm_batches(news_list)
                logger.info(f"LLM batch ranking complete, got {len(news_list)} news")
            except Exception as e:
                logger.error(f"LLM ranking failed, using fallback: {e}")
                news_list = self._fallback_selection(news_list)
        else:
            logger.info("LLM ranking disabled, using keyword scoring")
            news_list = self._keyword_scoring(news_list)

        return news_list

    def _rank_news_with_llm_batches(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """使用 LLM 分批评分"""
        # 分批处理
        batches = []
        for i in range(0, len(news_list), self.batch_size):
            batch = news_list[i:i + self.batch_size]
            batches.append(batch)

        logger.info(f"Split into {len(batches)} batches")

        # 每批选 Top N
        all_candidates = []
        for batch_idx, batch in enumerate(batches):
            try:
                selected = self._select_top_from_batch(batch, batch_idx)
                all_candidates.extend(selected)
                logger.info(f"Batch {batch_idx + 1}: selected {len(selected)} news")
            except Exception as e:
                logger.warning(f"Batch {batch_idx + 1} failed: {e}")
                # 失败的批次，简单取前 N 个
                all_candidates.extend(batch[:self.top_n_per_batch])

        logger.info(f"Collected {len(all_candidates)} candidates from batches")

        # 对所有候选进行关键词排序
        logger.info("Sorting all candidates by relevance (no final LLM selection)")
        all_candidates = self._keyword_scoring(all_candidates)

        return all_candidates

    def _select_top_from_batch(self, batch: List[NewsItem], batch_idx: int) -> List[NewsItem]:
        """从一批中选出 Top N"""
        prompt = self._build_batch_prompt(batch)

        response = self.chat([{"role": "user", "content": prompt}])
        if not response:
            raise Exception("No response from LLM")

        selected_indices = self._parse_selection_response(response)

        selected = []
        for idx in selected_indices:
            if 0 <= idx < len(batch):
                selected.append(batch[idx])

        # 如果选出的数量不够，补充一些
        if len(selected) < self.top_n_per_batch:
            for news in batch:
                if news not in selected and len(selected) < self.top_n_per_batch:
                    selected.append(news)

        return selected

    def _build_batch_prompt(self, batch: List[NewsItem]) -> str:
        """构建批次提示词"""
        lines = []

        if self.ranking_prompt:
            lines.append(self.ranking_prompt.format(top_n=self.top_n_per_batch))
        else:
            lines.append(f"请从以下新闻中选出最相关的 {self.top_n_per_batch} 条 AI 相关新闻，按相关度从高到低排序。")

        lines.append("")
        for i, news in enumerate(batch):
            lines.append(f"{i}. 标题: {news.title}")
            if news.source:
                lines.append(f"   来源: {news.source}")
            lines.append("")

        lines.append("请以 JSON 格式返回，格式如下：")
        lines.append('{"selected_indices": [0, 2, 5]}')

        return "\n".join(lines)

    def _parse_selection_response(self, response: str) -> List[int]:
        """解析 LLM 返回的选中索引"""
        # 尝试从响应中提取 JSON
        try:
            # 查找 JSON 对象
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                if "selected_indices" in data:
                    return [int(idx) for idx in data["selected_indices"]]
        except Exception as e:
            logger.debug(f"Failed to parse JSON: {e}")

        # 降级：尝试提取数字列表
        try:
            numbers = re.findall(r'\b\d+\b', response)
            if numbers:
                return [int(num) for num in numbers[:self.top_n_per_batch]]
        except Exception as e:
            logger.debug(f"Failed to parse numbers: {e}")

        raise Exception("Could not parse selection response")

    def _fallback_selection(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """降级方案：每个信源取 N 条"""
        logger.info(f"Using fallback selection: {self.fallback_per_source} per source")

        # 按信源分组
        news_by_source = {}
        for news in news_list:
            source = news.source or "unknown"
            if source not in news_by_source:
                news_by_source[source] = []
            news_by_source[source].append(news)

        # 每个信源取 N 条
        selected = []
        for source, source_news in news_by_source.items():
            # 按时间排序
            source_news.sort(
                key=lambda x: x.publish_time or x.created_at,
                reverse=True
            )
            selected.extend(source_news[:self.fallback_per_source])

        logger.info(f"Fallback selection got {len(selected)} news from {len(news_by_source)} sources")
        return selected

    def _keyword_scoring(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """简单关键词评分（备用）"""
        keywords = ["AI", "人工智能", "大模型", "GPT", "LLM", "机器学习", "深度学习",
                   "Agent", "Claude", "Gemini", "Sora", "文心", "通义", "智谱"]

        for news in news_list:
            score = 0.5
            title_lower = news.title.lower()
            for keyword in keywords:
                if keyword.lower() in title_lower:
                    score += 0.15
            news.ai_relevance_score = min(score, 1.0)

        # 按评分排序
        news_list.sort(
            key=lambda x: x.ai_relevance_score or 0,
            reverse=True
        )

        return news_list
