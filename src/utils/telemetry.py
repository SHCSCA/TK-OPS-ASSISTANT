import sentry_sdk
import logging
import config
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)

def init_sentry():
    """初始化 Sentry 错误监控"""
    if not config.SENTRY_DSN:
        logger.info("Sentry DSN 未配置，跳过初始化。")
        return

    try:
        sentry_logging = LoggingIntegration(
            level=logging.INFO,        # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors as events
        )

        sentry_sdk.init(
            dsn=config.SENTRY_DSN,
            release=f"tk-ops-assistant@{config.APP_VERSION}",
            integrations=[sentry_logging],
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            # We recommend adjusting this value in production.
            traces_sample_rate=1.0,
            # Set profiles_sample_rate to 1.0 to profile 100%
            # of sampled transactions.
            profiles_sample_rate=1.0,
            environment="production" if config.IS_FROZEN else "development",
        )
        logger.info("Sentry SDK 初始化成功")
    except Exception as e:
        logger.error(f"Sentry SDK 初始化失败: {e}")
