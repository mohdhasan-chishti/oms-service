"""
Basic Logging Filters for Rozana OMS (FastAPI)
"""
import logging
import uuid
from app.middlewares.request_context import request_context


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(request_context, 'request_id', str(uuid.uuid4()))
        # Inject HTTP method and path if present in context
        record.request_method = getattr(request_context, 'request_method', '')
        record.request_path = getattr(request_context, 'request_path', '')
        record.user_id = getattr(request_context, 'user_id', '')
        # Inject version headers if present in context
        record.app_version = getattr(request_context, 'app_version', '')
        record.web_version = getattr(request_context, 'web_version', '')
        return True


class BusinessContextFilter(logging.Filter):
    def filter(self, record):
        record.facility_id = getattr(request_context, 'facility_id', '')
        record.order_id = getattr(request_context, 'order_id', '')
        return True
