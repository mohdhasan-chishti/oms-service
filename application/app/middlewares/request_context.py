"""
Request context utilities for FastAPI using contextvars
"""
from contextvars import ContextVar
import uuid


class RequestContext:
    def __init__(self):
        self.request_id: str | None = None
        self.user_id: str | None = None
        self.facility_id: str | None = None
        self.order_id: str | None = None
        self.module_name: str | None = None
        self.request_method: str | None = None
        self.request_path: str | None = None
        self.app_version: str | None = None
        self.web_version: str | None = None


# Single shared context object stored in a ContextVar
_request_context_var: ContextVar[RequestContext] = ContextVar("request_context", default=RequestContext())


class _RequestContextProxy:
    def __getattr__(self, name):
        return getattr(_request_context_var.get(), name)

    def __setattr__(self, name, value):
        # ensure we set on current context instance
        setattr(_request_context_var.get(), name, value)


request_context = _RequestContextProxy()


def set_request_context(ctx: RequestContext):
    _request_context_var.set(ctx)


def clear_request_context():
    # Reset to a fresh context
    _request_context_var.set(RequestContext())


def create_request_id() -> str:
    rid = str(uuid.uuid4())
    request_context.request_id = rid
    return rid
