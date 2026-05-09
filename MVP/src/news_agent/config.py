from pathlib import Path
from typing import List, Optional, Union
import re

import yaml

# 检测 Pydantic 版本
try:
    from pydantic import BaseModel, Field, field_validator, model_validator
    from pydantic_settings import BaseSettings
    PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseModel, Field, validator
    from pydantic import BaseSettings
    PYDANTIC_V2 = False


class SchedulerConfig(BaseModel):
    cron_times: List[str] = Field(default_factory=lambda: ["08:30", "11:30", "17:30"])
    timezone: str = "Asia/Shanghai"

    if PYDANTIC_V2:
        @field_validator("cron_times")
        @classmethod
        def validate_cron_times(cls, v):
            """验证 cron 时间格式 HH:MM"""
            pattern = r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
            for time_str in v:
                if not re.match(pattern, time_str):
                    raise ValueError(f"Invalid cron time format: {time_str}, expected HH:MM")
            return v
    else:
        @validator("cron_times")
        def validate_cron_times(cls, v):
            """验证 cron 时间格式 HH:MM"""
            pattern = r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
            for time_str in v:
                if not re.match(pattern, time_str):
                    raise ValueError(f"Invalid cron time format: {time_str}, expected HH:MM")
            return v


class CrawlersConfig(BaseModel):
    enabled: List[str] = Field(default_factory=lambda: ["kr36", "aiera", "radar", "qbit"])
    timeout: int = 30
    request_delay: float = 2.0
    max_concurrent: int = 3

    if PYDANTIC_V2:
        @field_validator("timeout")
        @classmethod
        def validate_timeout(cls, v):
            if v <= 0:
                raise ValueError("timeout must be positive")
            return v

        @field_validator("request_delay")
        @classmethod
        def validate_request_delay(cls, v):
            if v < 0:
                raise ValueError("request_delay cannot be negative")
            return v

        @field_validator("max_concurrent")
        @classmethod
        def validate_max_concurrent(cls, v):
            if v < 1:
                raise ValueError("max_concurrent must be at least 1")
            if v > 10:
                raise ValueError("max_concurrent cannot exceed 10")
            return v
    else:
        @validator("timeout")
        def validate_timeout(cls, v):
            if v <= 0:
                raise ValueError("timeout must be positive")
            return v

        @validator("request_delay")
        def validate_request_delay(cls, v):
            if v < 0:
                raise ValueError("request_delay cannot be negative")
            return v

        @validator("max_concurrent")
        def validate_max_concurrent(cls, v):
            if v < 1:
                raise ValueError("max_concurrent must be at least 1")
            if v > 10:
                raise ValueError("max_concurrent cannot exceed 10")
            return v


class DatabaseConfig(BaseModel):
    path: str = "./data/news.db"


class LLMConfig(BaseModel):
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4"
    max_retries: int = 3
    timeout: int = 60
    use_llm_for_ranking: bool = True
    batch_size: int = 30
    top_n_per_batch: int = 10
    final_top_n: int = 20
    fallback_per_source: int = 10
    ranking_prompt: str = """请从以下新闻中选出最相关的 {top_n} 条 AI 相关新闻，按相关度从高到低排序。

请以 JSON 格式返回，格式如下：
{{"selected_indices": [0, 2, 5]}}"""

    if PYDANTIC_V2:
        @field_validator("base_url")
        @classmethod
        def validate_base_url(cls, v):
            if v and not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("base_url must start with http:// or https://")
            return v

        @field_validator("max_retries")
        @classmethod
        def validate_max_retries(cls, v):
            if v < 0:
                raise ValueError("max_retries cannot be negative")
            if v > 10:
                raise ValueError("max_retries cannot exceed 10")
            return v

        @field_validator("timeout")
        @classmethod
        def validate_timeout(cls, v):
            if v <= 0:
                raise ValueError("timeout must be positive")
            return v
    else:
        @validator("base_url")
        def validate_base_url(cls, v):
            if v and not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("base_url must start with http:// or https://")
            return v

        @validator("max_retries")
        def validate_max_retries(cls, v):
            if v < 0:
                raise ValueError("max_retries cannot be negative")
            if v > 10:
                raise ValueError("max_retries cannot exceed 10")
            return v

        @validator("timeout")
        def validate_timeout(cls, v):
            if v <= 0:
                raise ValueError("timeout must be positive")
            return v


class FeishuConfig(BaseModel):
    webhook_url: str = ""
    enabled: bool = True

    if PYDANTIC_V2:
        @field_validator("webhook_url")
        @classmethod
        def validate_webhook_url(cls, v, info):
            """如果启用了飞书，webhook_url 必须有效"""
            if info.data.get("enabled") and v:
                if not (v.startswith("http://") or v.startswith("https://")):
                    raise ValueError("webhook_url must start with http:// or https://")
            return v
    else:
        @validator("webhook_url")
        def validate_webhook_url(cls, v, values):
            """如果启用了飞书，webhook_url 必须有效"""
            if values.get("enabled") and v:
                if not (v.startswith("http://") or v.startswith("https://")):
                    raise ValueError("webhook_url must start with http:// or https://")
            return v


class Email163Config(BaseModel):
    sender: str = ""
    sender_name: str = "AI 新闻助手"
    password: str = ""
    recipients: List[str] = Field(default_factory=list)
    enabled: bool = True

    if PYDANTIC_V2:
        @field_validator("sender")
        @classmethod
        def validate_sender_email(cls, v, info):
            """如果启用了邮件，sender 必须有效"""
            if info.data.get("enabled") and v:
                if "@" not in v:
                    raise ValueError("sender must be a valid email address")
            return v

        @field_validator("recipients")
        @classmethod
        def validate_recipients(cls, v, info):
            """如果启用了邮件，recipients 必须有效"""
            if info.data.get("enabled") and v:
                for email in v:
                    if "@" not in email:
                        raise ValueError(f"Invalid email in recipients: {email}")
            return v
    else:
        @validator("sender")
        def validate_sender_email(cls, v, values):
            """如果启用了邮件，sender 必须有效"""
            if values.get("enabled") and v:
                if "@" not in v:
                    raise ValueError("sender must be a valid email address")
            return v

        @validator("recipients")
        def validate_recipients(cls, v, values):
            """如果启用了邮件，recipients 必须有效"""
            if values.get("enabled") and v:
                for email in v:
                    if "@" not in email:
                        raise ValueError(f"Invalid email in recipients: {email}")
            return v


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file_path: str = "./logs/news_agent.log"
    rotation: str = "50 MB"
    retention: str = "30 days"

    if PYDANTIC_V2:
        @field_validator("level")
        @classmethod
        def validate_log_level(cls, v):
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if v.upper() not in valid_levels:
                raise ValueError(f"Invalid log level: {v}, must be one of {valid_levels}")
            return v.upper()
    else:
        @validator("level")
        def validate_log_level(cls, v):
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if v.upper() not in valid_levels:
                raise ValueError(f"Invalid log level: {v}, must be one of {valid_levels}")
            return v.upper()


class Config(BaseSettings):
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    crawlers: CrawlersConfig = Field(default_factory=CrawlersConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    email_163: Email163Config = Field(default_factory=Email163Config)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def from_yaml(cls, config_path: Union[Path, str]) -> "Config":
        """从 YAML 文件加载配置"""
        config_path = Path(config_path)
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if PYDANTIC_V2:
            return cls.model_validate(data)
        else:
            return cls.parse_obj(data)


# 全局配置实例
_config: Optional[Config] = None


def get_config(config_path: Union[Path, str, None] = None) -> Config:
    """获取全局配置实例"""
    global _config
    if _config is None:
        if config_path is None:
            # 默认配置路径
            config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
        _config = Config.from_yaml(config_path)
    return _config


def set_config(config: Config) -> None:
    """设置全局配置实例"""
    global _config
    _config = config
