from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import firebase_admin

from app.utils.firebase_auth_cache import extract_bearer_token, verify_id_token_with_cache
app_instance = firebase_admin.get_app("app")

class FirebaseAuthMiddlewareAPP(BaseHTTPMiddleware):
    """Validate Firebase ID tokens and attach user info to `request.state`."""

    include_path_start = "/app/v1"

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        if not request.url.path.startswith(self.include_path_start):
            return await call_next(request)

        auth_header = request.headers.get("authorization")
        token = extract_bearer_token(auth_header)
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        try:
            decoded_token = verify_id_token_with_cache(token, app_instance)
            request.state.user_id = decoded_token.get("user_id")
            request.state.phone_number = decoded_token.get("phone_number")
        except Exception:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        return await call_next(request)
