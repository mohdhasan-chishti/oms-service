from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import os
import traceback
from typing import Any
from app.config.sentry import capture_exception, capture_message, add_breadcrumb
from app.logging.utils import get_app_logger
from app.middlewares.request_context import request_context

logger = get_app_logger(__name__)

# Debug mode detection (DEBUG=false means production)
DEBUG = os.getenv("DEBUG", "true").lower() == "true"


async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with production-safe messages."""
    # annotate module context
    request_context.module_name = 'middleware_handlers'
    # Log detailed error for debugging
    logger.warning(f"validation_error | method={request.method} url={str(request.url)} errors={exc.errors()}",exc_info=True,)
    
    # Add breadcrumb for Sentry
    add_breadcrumb(
        message=f"Validation error on {request.method} {request.url}",
        category="validation",
        level="error",
        data={"errors": exc.errors()}
    )
    
    # Capture exception in Sentry
    capture_exception(exc)

    if not DEBUG:
        # Generic message in production (DEBUG=false)
        payload = {"message": "Invalid request data"}
    else:
        # Detailed messages in debug mode (DEBUG=true)
        # Format errors in single readable line: "field_path: error_message"
        error_messages = []
        for err in exc.errors():
            field_path = " -> ".join(str(loc) for loc in err.get("loc", []))
            error_msg = err.get("msg", "Invalid input")
            error_messages.append(f"{field_path}: {error_msg}")

        # Return single message if one error, list if multiple
        if len(error_messages) == 1:
            payload = {"message": error_messages[0]}
        else:
            payload = {"message": "Validation errors", "errors": error_messages}

    logger.error(f"validation_error | method={request.method} url={str(request.url)} errors={payload}", exc_info=True)
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)


async def _general_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with production-safe messages."""
    # annotate module context and log with traceback
    request_context.module_name = 'middleware_handlers'
    logger.error(
        f"unhandled_exception | method={request.method} url={str(request.url)} exception_type={type(exc).__name__} exception_message={str(exc)}",
        exc_info=True,
    )
    
    # Add breadcrumb for Sentry
    add_breadcrumb(
        message=f"Unhandled exception on {request.method} {request.url}",
        category="exception",
        level="error",
        data={"exception_type": type(exc).__name__, "exception_message": str(exc)}
    )
    
    # Capture exception in Sentry
    capture_exception(exc)
    
    if not DEBUG:
        # Generic message in production (DEBUG=false)
        payload = {"message": "Something went wrong"}
    else:
        # Detailed error in debug mode (DEBUG=true)
        payload = {"message": f"Internal server error: {str(exc)}"}
    
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


async def _http_exception_handler(request: Request, exc: Any):
    """Handle HTTP exceptions with production-safe messages."""
    # annotate module context and determine status
    request_context.module_name = 'middleware_handlers'
    status_code = getattr(exc, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)
    # Log 5xx as errors (with traceback) and 4xx as warnings
    if status_code >= 500:
        logger.error(f"http_exception | method={request.method} url={str(request.url)} status_code={status_code} detail={getattr(exc, 'detail', str(exc))}",exc_info=True,)
    else:
        logger.warning(f"http_exception | method={request.method} url={str(request.url)} status_code={status_code} detail={getattr(exc, 'detail', str(exc))}",exc_info=True,)
    
    # Add breadcrumb for Sentry (only for server errors, not client errors)
    if status_code >= 500:
        add_breadcrumb(
            message=f"HTTP {status_code} error on {request.method} {request.url}",
            category="http",
            level="error",
            data={"status_code": status_code, "detail": getattr(exc, 'detail', str(exc))}
        )
        # Capture exception in Sentry for server errors
        capture_exception(exc)
    
    if not DEBUG:
        # Generic messages based on status code in production (DEBUG=false)
        if status_code == 404:
            message = "Resource not found"
        elif status_code == 403:
            message = "Access denied"
        elif status_code == 401:
            message = "Authentication required"
        elif 400 <= status_code < 500:
            message = "Invalid request"
        else:
            message = "Something went wrong"
        payload = {"message": message}
    else:
        # Detailed error in debug mode (DEBUG=true)
        detail = getattr(exc, 'detail', str(exc))
        payload = {"message": detail}
    
    return JSONResponse(status_code=status_code, content=payload)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all custom exception handlers to the given FastAPI instance."""
    from fastapi.exceptions import HTTPException
    
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _general_exception_handler)