from datetime import datetime
from typing import Optional

# 检测 Pydantic 版本
try:
    from pydantic import BaseModel, Field
    PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseModel, Field
    PYDANTIC_V2 = False


class NewsItem(BaseModel):
    """新闻数据模型"""
    title: str = Field(..., description="新闻标题")
    url: str = Field(..., description="新闻链接")
    cover_image: Optional[str] = Field(None, description="新闻封面图")
    publish_time: Optional[datetime] = Field(None, description="发布时间")
    source: str = Field(..., description="来源网站")
    content: Optional[str] = Field(None, description="新闻内容")
    ai_relevance_score: Optional[float] = Field(None, description="AI 相关度评分（0-1）")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    sent_at: Optional[datetime] = Field(None, description="发送时间")

    if PYDANTIC_V2:
        model_config = {
            "json_encoders": {
                datetime: lambda v: v.isoformat() if v else None
            }
        }
    else:
        class Config:
            json_encoders = {
                datetime: lambda v: v.isoformat() if v else None
            }

    def to_dict(self) -> dict:
        """转换为字典"""
        if PYDANTIC_V2:
            return self.model_dump()
        else:
            return self.dict()

    @classmethod
    def from_dict(cls, data: dict) -> "NewsItem":
        """从字典创建"""
        if PYDANTIC_V2:
            return cls.model_validate(data)
        else:
            return cls.parse_obj(data)
