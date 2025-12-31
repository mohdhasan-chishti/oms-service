"""
Logging Handlers for Rozana OMS (FastAPI)
Firehose-backed buffered handlers with local-file fallback.
"""
import logging
import time
from logging.handlers import MemoryHandler
import os

import boto3
from botocore.config import Config

from app.logging.config import LoggingConfig
from app.logging.formatters import AppLogsJSONFormatter, AuditLogsJSONFormatter

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()

LOG_DEBUG_PRINTS = configs.LOG_DEBUG_PRINTS

def dbg(msg: str) -> None:
    """Lightweight debug print; enabled when LOG_DEBUG_PRINTS=1"""
    if LOG_DEBUG_PRINTS:
        print(msg)

class FireHoseHandler(logging.Handler):
    """Kinesis Firehose handler with simple retries"""

    def __init__(self, stream_name: str):
        super().__init__()
        self.stream_name = stream_name
        self.client = self._create_client()
        self.retry_count = LoggingConfig.FIREHOSE_RETRY_COUNT
        self.retry_delay = LoggingConfig.FIREHOSE_RETRY_DELAY

    def _create_client(self):
        return boto3.client(
            "firehose",
            region_name=LoggingConfig.FIREHOSE_REGION_NAME,
            aws_access_key_id=LoggingConfig.FIREHOSE_ACCESS_KEY_ID,
            aws_secret_access_key=LoggingConfig.FIREHOSE_SECRET_ACCESS_KEY,
            config=Config(connect_timeout=10, read_timeout=30, retries={"max_attempts": 2}),
        )

    def bulk_insert(self, actions):
        if not actions:
            return True

        for attempt in range(self.retry_count):
            try:
                response = self.client.put_record_batch(
                    DeliveryStreamName=self.stream_name,
                    Records=actions,
                )
                failed = response.get("FailedPutCount", 0)
                dbg(f"[Firehose:{self.stream_name}] put_record_batch attempt={attempt+1} total={len(actions)} failed={failed}")
                if failed == 0:
                    dbg(f"[Firehose:{self.stream_name}] batch success")
                    return True
                # retry only failed ones
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
            except Exception:
                dbg(f"[Firehose:{self.stream_name}] exception on attempt={attempt+1}, will_retry={attempt < self.retry_count - 1}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                else:
                    return False
        return False


class SimpleMemoryHandler(MemoryHandler):
    def __init__(self, capacity, target_handler, stream_name):
        super().__init__(capacity=capacity, target=target_handler)
        self.stream_name = stream_name
        self.buffer_timeout = LoggingConfig.LOG_BUFFER_TIMEOUT
        self.last_flush = time.time()

    def emit(self, record):
        pre_len = len(self.buffer)
        super().emit(record)
        dbg(f"[Buffer:{self.stream_name}] emit size_before={pre_len} size_after={len(self.buffer)} capacity={self.capacity}")
        now = time.time()
        if now - self.last_flush >= self.buffer_timeout or len(self.buffer) >= self.capacity:
            reason = "timeout" if (now - self.last_flush) >= self.buffer_timeout else "capacity"
            dbg(f"[Buffer:{self.stream_name}] triggering flush reason={reason} age_ms={(now - self.last_flush)*1000:.0f} size={len(self.buffer)}")
            self.flush()

    def flush(self):
        self.acquire()
        try:
            if self.target and self.buffer:
                dbg(f"[Buffer:{self.stream_name}] flushing count={len(self.buffer)}")
                actions = []
                for record in self.buffer:
                    payload = self.format(record)
                    actions.append({"Data": payload})
                if actions:
                    ok = self.target.bulk_insert(actions)
                    dbg(f"[Buffer:{self.stream_name}] flush result ok={ok}")
                self.buffer.clear()
                self.last_flush = time.time()
        finally:
            self.release()


class AppLogsMemoryHandler(SimpleMemoryHandler):
    def __init__(self, stream_name: str):
        target = FireHoseHandler(stream_name)
        super().__init__(capacity=LoggingConfig.APP_LOGS_CAPACITY, target_handler=target, stream_name=stream_name)
        fmt = AppLogsJSONFormatter()
        self.setFormatter(fmt)
        target.setFormatter(fmt)


class AuditLogsMemoryHandler(SimpleMemoryHandler):
    def __init__(self, stream_name: str):
        target = FireHoseHandler(stream_name)
        super().__init__(capacity=LoggingConfig.AUDIT_LOGS_CAPACITY, target_handler=target, stream_name=stream_name)
        fmt = AuditLogsJSONFormatter()
        self.setFormatter(fmt)
        target.setFormatter(fmt)


_handlers = {}

def get_local_file_handler(name: str = 'app'):
    import os
    os.makedirs('logs', exist_ok=True)
    handler = logging.FileHandler(f'logs/{name}.log')
    formatter = AppLogsJSONFormatter() if name == 'app' else AuditLogsJSONFormatter()
    handler.setFormatter(formatter)
    return handler


def get_app_handler():
    if LoggingConfig.FIREHOSE_ENABLED:
        if 'app' not in _handlers:
            stream = LoggingConfig.APP_LOGS_STREAM_NAME or 'rozana-oms-app-logs'
            _handlers['app'] = AppLogsMemoryHandler(stream)
        return _handlers['app']
    else:
        return get_local_file_handler('app')


def get_audit_handler(method: str = ''):
    if LoggingConfig.FIREHOSE_ENABLED:
        if method == 'GET':
            key = 'audit_get'
            stream = LoggingConfig.AUDIT_LOGS_GET_STREAM_NAME or 'rozana-oms-audit-get-logs'
        else:
            key = 'audit_all'
            stream = LoggingConfig.AUDIT_LOGS_STREAM_NAME or 'rozana-oms-audit-logs'
        if key not in _handlers:
            _handlers[key] = AuditLogsMemoryHandler(stream)
        return _handlers[key]
    else:
        return get_local_file_handler('audit_logs_backup')
