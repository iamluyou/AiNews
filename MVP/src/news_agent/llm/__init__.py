from .base import BaseLLM
from .client import OpenAIClient

# LLM 注册表
LLM_REGISTRY = {
    "openai": OpenAIClient,
}


def create_llm_from_config(config) -> "BaseLLM | None":
    """根据配置创建 LLM 客户端

    Args:
        config: Config 配置对象

    Returns:
        LLM 实例，如果未配置则返回 None
    """
    from ..utils.logger import get_logger
    logger = get_logger(__name__)

    if not config.llm.api_key:
        return None

    llm = OpenAIClient(
        base_url=config.llm.base_url,
        api_key=config.llm.api_key,
        model=config.llm.model,
        max_retries=config.llm.max_retries,
        timeout=config.llm.timeout,
        ranking_prompt=config.llm.ranking_prompt,
        use_llm_for_ranking=config.llm.use_llm_for_ranking,
        batch_size=config.llm.batch_size,
        top_n_per_batch=config.llm.top_n_per_batch,
        final_top_n=config.llm.final_top_n,
        fallback_per_source=config.llm.fallback_per_source,
    )
    logger.info("Loaded LLM client")
    return llm


__all__ = ["BaseLLM", "OpenAIClient", "LLM_REGISTRY", "create_llm_from_config"]
