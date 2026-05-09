import sys
from pathlib import Path
from typing import Optional, Union
from loguru import logger


def get_logger(name: str = "news_agent"):
    """获取配置好的 logger"""
    return logger.bind(name=name)


def setup_logger(log_file: Optional[Union[Path, str]] = None, level: str = "INFO"):
    """配置 logger"""
    # 移除默认 handler
    logger.remove()

    # 添加控制台输出
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[name]}</cyan> | <level>{message}</level>",
        level=level,
    )

    # 添加文件输出
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_path,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]} | {message}",
            level=level,
            rotation="50 MB",
            retention="30 days",
            encoding="utf-8",
        )


# 默认初始化
setup_logger()
