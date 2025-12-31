import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

import logging

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("sentry")

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()


def init_sentry():
    """Initialize Sentry SDK with flag-based configuration"""
    
    # Check if Sentry is enabled via environment flag
    sentry_enabled = configs.SENTRY_ENABLED
    
    if not sentry_enabled:
        logger.info("Sentry monitoring is disabled")
        return
    
    # Get Sentry DSN from environment
    sentry_dsn = configs.SENTRY_DSN
    
    if not sentry_dsn:
        logger.warning("SENTRY_ENABLED is true but SENTRY_DSN is not configured")
        return
    
    # Get environment and release info
    environment = configs.ENVIRONMENT   
    release = configs.SENTRY_RELEASE
    
    # Configure Sentry
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=environment,
        release=release,
        traces_sample_rate=float(configs.SENTRY_TRACES_SAMPLE_RATE),
        profiles_sample_rate=float(configs.SENTRY_PROFILES_SAMPLE_RATE),
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(
                level=logging.INFO,        # Capture info and above as breadcrumbs
                event_level=logging.ERROR  # Send errors as events
            ),
        ],
        # Performance monitoring
        enable_tracing=True,
        # Send default PII (personally identifiable information)
        send_default_pii=False,
        # Attach stack traces to all messages
        attach_stacktrace=True,
        # Sample rate for error events
        sample_rate=1.0,
        # Maximum breadcrumbs
        max_breadcrumbs=50,
        # Before send hook to filter sensitive data
        before_send=before_send_filter,
    )
    
    logger.info(f"Sentry initialized successfully for environment: {environment}")


def before_send_filter(event, hint):
    """Filter sensitive data before sending to Sentry"""
    
    # Remove sensitive headers
    if 'request' in event and 'headers' in event['request']:
        sensitive_headers = ['authorization', 'cookie', 'x-api-key', 'x-auth-token']
        headers = event['request']['headers']
        for header in sensitive_headers:
            if header in headers:
                headers[header] = '[Filtered]'
    
    # Filter sensitive form data
    if 'request' in event and 'data' in event['request']:
        sensitive_fields = ['password', 'token', 'secret', 'key', 'auth']
        data = event['request']['data']
        if isinstance(data, dict):
            for field in sensitive_fields:
                for key in list(data.keys()):
                    if field.lower() in key.lower():
                        data[key] = '[Filtered]'
    
    return event


def capture_exception(exception, **kwargs):
    """Wrapper to capture exceptions only if Sentry is enabled"""
    sentry_enabled = configs.SENTRY_ENABLED

    if sentry_enabled:
        sentry_sdk.capture_exception(exception, **kwargs)
        logger.error(f"Exception occurred: {exception}", exc_info=True)
    else:
        # Log locally if Sentry is disabled
        logger.error(f"Exception occurred: {exception}", exc_info=True)


def capture_message(message, level="info", **kwargs):
    """Wrapper to capture messages only if Sentry is enabled"""
    sentry_enabled = configs.SENTRY_ENABLED

    if sentry_enabled:
        sentry_sdk.capture_message(message, level=level, **kwargs)
    else:
        # Log locally if Sentry is disabled
        getattr(logger, level.lower(), logger.info)(message)


def add_breadcrumb(message, category="custom", level="info", data=None):
    """Wrapper to add breadcrumbs only if Sentry is enabled"""
    sentry_enabled = configs.SENTRY_ENABLED

    if sentry_enabled:
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {}
        )
