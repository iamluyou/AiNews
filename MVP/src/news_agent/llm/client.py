from typing import List, Optional
import time

from openai import OpenAI

from .base import BaseLLM
from ..utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIClient(BaseLLM):
    """OpenAI 兼容客户端"""

    name = "openai"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "gpt-4",
        max_retries: int = 3,
        timeout: int = 60,
        ranking_prompt: Optional[str] = None,
        use_llm_for_ranking: bool = True,
        batch_size: int = 30,
        top_n_per_batch: int = 10,
        final_top_n: int = 20,
        fallback_per_source: int = 10,
    ):
        super().__init__(
            ranking_prompt=ranking_prompt,
            use_llm_for_ranking=use_llm_for_ranking,
            batch_size=batch_size,
            top_n_per_batch=top_n_per_batch,
            final_top_n=final_top_n,
            fallback_per_source=fallback_per_source,
        )
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

    def chat(self, messages: List[dict], **kwargs) -> Optional[str]:
        """对话接口"""
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    messages=messages,
                    model=kwargs.get("model", self.model),
                    temperature=kwargs.get("temperature", 0.7),
                    max_tokens=kwargs.get("max_tokens", 2000),
                )
                if attempt > 0:
                    logger.info(f"Chat succeeded on attempt {attempt + 1}")
                return response.choices[0].message.content
            except Exception as e:
                wait_time = 2 ** attempt
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Chat attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Chat failed after {self.max_retries} attempts. "
                        f"Last error: {e}"
                    )
                    return None
        return None

    def batch_chat(self, prompts: List[str], **kwargs) -> List[Optional[str]]:
        """批量对话接口（串行实现，实际可优化为并行）"""
        results = []
        for prompt in prompts:
            result = self.chat([{"role": "user", "content": prompt}], **kwargs)
            results.append(result)
        return results
