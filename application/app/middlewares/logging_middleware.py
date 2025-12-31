"""
Audit and Request Logging Middleware for FastAPI (Rozana OMS)
Mirrors the Potions AuditMiddleware behavior using Starlette's BaseHTTPMiddleware.
"""
import json
import os
import socket
import time
from datetime import datetime
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.logging.utils import get_app_logger, init_audit_logger
from app.logging.config import LoggingConfig
from app.middlewares.request_context import create_request_id, request_context, clear_request_context

# settings 
from app.config.settings import OMSConfigs
configs = OMSConfigs()

APP_NAME = configs.APP_NAME
APP_VERSION = configs.APP_VERSION

class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exclude_paths: list[str] | None = None):
        super().__init__(app)
        self.logger = get_app_logger('app.logging')
        self.exclude_audit_paths = exclude_paths or ['/health', '/docs', '/redoc']
        self.hostname = socket.gethostname()
        self.app_name = APP_NAME
        self.version = APP_VERSION

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            request_id = create_request_id()
            start_time = time.time()
            timestamp = datetime.now().isoformat()

            # read body safely (only once)
            body_bytes = await request.body()

            # module name not directly applicable; keep optional
            request_context.module_name = None
            # inject basic http context for filters/formatters
            request_context.request_method = request.method
            request_context.request_path = request.url.path       
            # Extract version headers for logging
            request_context.app_version = request.headers.get('x-app-version', '')
            request_context.web_version = request.headers.get('x-web-version', '')


            should_audit = LoggingConfig.AUDIT_LOGGING_ENABLED and not any(
                request.url.path.startswith(p) for p in self.exclude_audit_paths
            )

            try:
                response = await call_next(request)
                duration = (time.time() - start_time) * 1000

                if should_audit:
                    audit_data = self._build_audit_data(request, response, body_bytes, duration, request_id, timestamp)
                    audit_logger = self._get_audit_logger_for_method(request.method)
                    # Match Potions: push data via 'extra' and ignore message content in formatter
                    audit_logger.info("Audit log", extra=audit_data)
                return response
            except Exception as exc:  # noqa: BLE001
                duration = (time.time() - start_time) * 1000
                self.logger.error(
                    f"Exception: {request.method} {request.url.path} - {exc.__class__.__name__} ({duration:.0f}ms)",
                    exc_info=True,
                )
                if should_audit:
                    # Build minimal error response details
                    fake_response = Response(status_code=500)
                    audit_data = self._build_audit_data(request, fake_response, body_bytes, duration, request_id, timestamp)
                    audit_data['exception'] = exc.__class__.__name__
                    audit_logger = self._get_audit_logger_for_method(request.method)
                    audit_logger.info("Audit log (exception)", extra=audit_data)
                raise
            finally:
                clear_request_context()
        except Exception:
            # last resort: do not block request
            try:
                return await call_next(request)
            except Exception:
                return Response(content="Internal Server Error", status_code=500)

    def _get_audit_logger_for_method(self, method: str):
        if method.upper() == 'GET':
            stream_name = LoggingConfig.AUDIT_LOGS_GET_STREAM_NAME
        else:
            stream_name = LoggingConfig.AUDIT_LOGS_STREAM_NAME
        return init_audit_logger(stream_name)

    def _mask_headers(self, headers) -> dict:
        """Mask Authorization header before logging.

        Always replaces any Authorization header value with '****'.
        """
        try:
            return {
                k: ('****' if k.lower() == 'authorization' else v)
                for k, v in headers.items()
            }
        except Exception:  # noqa: BLE001
            # Fallback: avoid breaking request flow due to header masking
            try:
                return dict(headers)
            except Exception:  # noqa: BLE001
                return {}

    def _build_audit_data(
        self,
        request: Request,
        response: Response,
        body_bytes: bytes,
        duration: float,
        request_id: str,
        timestamp: str,
    ) -> dict:
        # parse request body
        try:
            if body_bytes:
                content_type = request.headers.get('content-type', '')
                if 'application/json' in content_type:
                    body_data = json.loads(body_bytes.decode('utf-8'))
                else:
                    body_data = body_bytes.decode('utf-8')[:1000]
            else:
                body_data = {}
        except Exception:  # noqa: BLE001
            body_data = {}

        # response data: capture only for non-2xx and when flag is enabled
        try:
            status = getattr(response, 'status_code', 0)
            is_2xx = 200 <= status < 300
            capture_body = LoggingConfig.CAPTURE_RESPONSE_BODY and not is_2xx
            resp_ct = response.headers.get('content-type', '') if hasattr(response, 'headers') else ''
            if not capture_body:
                response_data = ''
            else:
                if hasattr(response, 'body_iterator'):
                    # cannot consume iterator here safely; skip content for streamed responses
                    response_data = ''
                elif hasattr(response, 'body') and response.body is not None:
                    if 'application/json' in resp_ct:
                        response_data = json.loads(response.body.decode('utf-8'))
                    else:
                        response_data = response.body.decode('utf-8')[:1000]
                else:
                    response_data = ''
        except Exception:  # noqa: BLE001
            response_data = ''

        size_in_bytes = 0
        try:
            if hasattr(response, 'body') and response.body is not None:
                size_in_bytes = len(response.body)
        except Exception:
            size_in_bytes = 0

        request_json = {
            "GET": dict(request.query_params),
            "POST": {},
            "BODY": body_data,
            "HEADERS": self._mask_headers(dict(request.headers)),
        }

        return {
            'duration': round(duration, 2),
            'header_referer': request.headers.get('referer', ''),
            'hostname': self.hostname,
            'app_name': self.app_name,
            'module_name': request_context.module_name,
            'request': request_json,
            'request_id': request_id,
            'request_method': request.method,
            'request_path': request.url.path,
            'response': response_data,
            'size_in_bytes': size_in_bytes,
            'status_code': getattr(response, 'status_code', 0),
            'timestamp': timestamp,
            'version': self.version,
            'app_version': request_context.app_version,
            'web_version': request_context.web_version,
        }
