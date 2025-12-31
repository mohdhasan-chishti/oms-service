"""
Logging utilities for Rozana OMS (FastAPI)
Mirrors Potions logging API with minimal differences.
"""
import logging
import atexit

from app.logging.config import LoggingConfig
from app.logging.handlers import get_app_handler, get_audit_handler, get_local_file_handler
from app.logging.filters import RequestContextFilter, BusinessContextFilter
from app.logging.slack_handler import slack_handler


def setup_app_logging(logger_name: str):
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()

    handler = get_app_handler()
    handler.addFilter(RequestContextFilter())
    handler.addFilter(BusinessContextFilter())

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def setup_audit_logging(logger_name: str):
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()

    handler = get_audit_handler()
    handler.addFilter(RequestContextFilter())

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def get_logger(log_type: str = 'app', logger_name: str = 'oms'):
    full_name = f"{logger_name}.{log_type}" if log_type != 'app' else logger_name
    logger = logging.getLogger(full_name)
    if logger.handlers:
        return logger
    if log_type == 'audit':
        return setup_audit_logging(full_name)
    else:
        return setup_app_logging(full_name)


essential_app_logger = None

def get_app_logger(name: str | None = None):
    global essential_app_logger
    if name:
        logger = logging.getLogger(name)
        if not logger.handlers:
            logger.handlers.clear()
            # central handler or local file handler per module
            handler = get_app_handler() if LoggingConfig.FIREHOSE_ENABLED else get_local_file_handler(name.replace('.', '_'))
            handler.addFilter(RequestContextFilter())
            handler.addFilter(BusinessContextFilter())
            logger.addHandler(handler)
            logger.addHandler(slack_handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False
        return logger
    if essential_app_logger is None:
        essential_app_logger = get_logger('app', 'oms')
    return essential_app_logger


def init_audit_logger(stream_name: str | None = None):
    if stream_name:
        logger_name = f"oms.audit.{stream_name.replace('-', '_')}"
        logger = logging.getLogger(logger_name)
        if not logger.handlers:
            logger.handlers.clear()
            handler = get_audit_handler()
            handler.addFilter(RequestContextFilter())
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False
        return logger
    return get_logger('audit', 'oms')


def initialize_logging():
    try:
        is_valid, message = LoggingConfig.is_valid_config()
        if not is_valid:
            print(f"Warning: {message}")
        # If we add async processors in future, register shutdown hook here
        atexit.register(lambda: None)
        print("Logging system initialized (OMS)")
    except Exception as e:
        print(f"Failed to initialize logging: {e}")
        raise
