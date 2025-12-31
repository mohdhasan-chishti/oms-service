"""
JSON Formatters for Rozana OMS Logging (FastAPI)
Simplified and aligned with Potions service
"""
import json
import logging
import os
from datetime import datetime
 
# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()

APPLICATION_ENVIRONMENT = configs.APPLICATION_ENVIRONMENT

class BaseJSONFormatter(logging.Formatter):
    """Basic JSON formatter"""

    def __init__(self):
        super().__init__()
        self.application_environment = APPLICATION_ENVIRONMENT

    def format(self, record):
        """Convert log record to JSON format"""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line_number': record.lineno,
            'environment': self.application_environment,
            'service': 'rozana-oms'
        }

        # Add exception if present
        if record.exc_info:
            log_entry['exception'] = str(record.exc_info[1])

        # Add extra fields from record
        self.add_extra_fields(log_entry, record)

        return json.dumps(log_entry, ensure_ascii=False, default=str)

    def add_extra_fields(self, log_entry, record):
        pass


class AppLogsJSONFormatter(BaseJSONFormatter):
    def add_extra_fields(self, log_entry, record):
        log_entry['request_id'] = getattr(record, 'request_id', '')
        log_entry['user_id'] = getattr(record, 'user_id', '')
        log_entry['order_id'] = getattr(record, 'order_id', '')
        log_entry['facility_id'] = getattr(record, 'facility_id', '')
        log_entry['app_version'] = getattr(record, 'app_version', '')
        log_entry['web_version'] = getattr(record, 'web_version', '')


class AuditLogsJSONFormatter(BaseJSONFormatter):
    def format(self, record):
        """Override to exclude the raw 'message' field for audit logs.
        We still include core metadata and extras populated below.
        """
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line_number': record.lineno,
            'environment': self.application_environment,
            'service': 'rozana-oms'
        }

        if record.exc_info:
            log_entry['exception'] = str(record.exc_info[1])

        self.add_extra_fields(log_entry, record)
        return json.dumps(log_entry, ensure_ascii=False, default=str)

    def add_extra_fields(self, log_entry, record):
        # Common identifiers
        log_entry['user_id'] = getattr(record, 'user_id', '')
        log_entry['request_id'] = getattr(record, 'request_id', '')

        # Meta/context
        log_entry['duration'] = getattr(record, 'duration', 0.0)
        log_entry['header_referer'] = getattr(record, 'header_referer', '')
        log_entry['hostname'] = getattr(record, 'hostname', '')
        log_entry['app_name'] = getattr(record, 'app_name', '')
        log_entry['module_name'] = getattr(record, 'module_name', '')

        # Request/Response (store serialized)
        request_data = getattr(record, 'request', None)
        response_data = getattr(record, 'response', None)
        log_entry['request'] = json.dumps(request_data, ensure_ascii=False, default=str) if request_data else ''
        log_entry['response'] = json.dumps(response_data, ensure_ascii=False, default=str) if response_data else ''

        # HTTP fields
        log_entry['request_method'] = getattr(record, 'request_method', '')
        log_entry['request_path'] = getattr(record, 'request_path', '')
        log_entry['size_in_bytes'] = getattr(record, 'size_in_bytes', 0)
        log_entry['status_code'] = getattr(record, 'status_code', 0)
        log_entry['version'] = getattr(record, 'version', '')
        log_entry['app_version'] = getattr(record, 'app_version', '')
        log_entry['web_version'] = getattr(record, 'web_version', '')
