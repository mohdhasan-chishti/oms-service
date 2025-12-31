"""
Simplified Logging Configuration for Rozana OMS (FastAPI)
Aligned with Potions logging design: Firehose-first with local fallback.
"""
import os

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()

class LoggingConfig:
    """Simplified logging configuration - firehose only"""

    # Core settings
    ASYNC_LOGGING = configs.ASYNC_LOGGING
    BATCH_PROCESSING = configs.BATCH_PROCESSING
    FIREHOSE_ENABLED = configs.FIREHOSE_ENABLED
    AUDIT_LOGGING_ENABLED = configs.AUDIT_LOGGING_ENABLED
    CAPTURE_RESPONSE_BODY = configs.CAPTURE_RESPONSE_BODY

    # Stream Names
    APP_LOGS_STREAM_NAME = configs.APP_LOGS_STREAM_NAME
    AUDIT_LOGS_STREAM_NAME = configs.AUDIT_LOGS_STREAM_NAME
    AUDIT_LOGS_GET_STREAM_NAME = configs.AUDIT_LOGS_GET_STREAM_NAME
    LOG_BUFFER_TIMEOUT = configs.LOG_BUFFER_TIMEOUT

    # Buffer sizes
    APP_LOGS_CAPACITY = configs.APP_LOGS_CAPACITY
    AUDIT_LOGS_CAPACITY = configs.AUDIT_LOGS_CAPACITY
    AUDIT_LOGS_GET_CAPACITY = configs.AUDIT_LOGS_GET_CAPACITY
    LOG_PROCESSOR_POOL_SIZE = configs.LOG_PROCESSOR_POOL_SIZE
    MAX_QUEUE_SIZE = configs.MAX_QUEUE_SIZE

    # Firehose settings
    FIREHOSE_REGION_NAME = configs.FIREHOSE_REGION_NAME
    FIREHOSE_ACCESS_KEY_ID = configs.FIREHOSE_ACCESS_KEY_ID
    FIREHOSE_SECRET_ACCESS_KEY = configs.FIREHOSE_SECRET_ACCESS_KEY
    FIREHOSE_RETRY_COUNT = configs.FIREHOSE_RETRY_COUNT
    FIREHOSE_RETRY_DELAY = configs.FIREHOSE_RETRY_DELAY

    @classmethod
    def is_valid_config(cls):
        """Validate configuration - only check Firehose when enabled"""
        if cls.FIREHOSE_ENABLED:
            if not cls.FIREHOSE_ACCESS_KEY_ID or not cls.FIREHOSE_SECRET_ACCESS_KEY:
                return False, "Firehose credentials not configured"
        return True, "Configuration is valid"
