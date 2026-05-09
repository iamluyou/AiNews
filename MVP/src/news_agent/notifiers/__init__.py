from .base import BaseNotifier
from .feishu import FeishuNotifier
from .email_163 import Email163Notifier

# 通知器注册表
NOTIFIER_REGISTRY = {
    "feishu": FeishuNotifier,
    "email_163": Email163Notifier,
}


def create_notifiers_from_config(config) -> list:
    """根据配置创建通知器列表

    Args:
        config: Config 配置对象

    Returns:
        通知器实例列表
    """
    from ..utils.logger import get_logger
    logger = get_logger(__name__)

    notifiers = []

    if config.feishu.enabled and config.feishu.webhook_urls:
        notifiers.append(FeishuNotifier(config.feishu.webhook_urls))
        logger.info(f"Loaded Feishu notifier with {len(config.feishu.webhook_urls)} webhooks")

    if config.email_163.enabled and config.email_163.sender:
        notifiers.append(
            Email163Notifier(
                sender=config.email_163.sender,
                sender_name=config.email_163.sender_name,
                password=config.email_163.password,
                recipients=config.email_163.recipients,
            )
        )
        logger.info("Loaded Email163 notifier")

    return notifiers


__all__ = ["BaseNotifier", "FeishuNotifier", "Email163Notifier", "NOTIFIER_REGISTRY", "create_notifiers_from_config"]
