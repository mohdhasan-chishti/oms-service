from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import os
from app.logging.utils import get_app_logger

logger = get_app_logger(__name__)

class APITokenValidationMiddleware(BaseHTTPMiddleware):
    
    include_path_start = "/api/v1"
    
    def __init__(self, app):
        super().__init__(app)
        self.auth_service_url = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")
        if not self.auth_service_url.endswith("/"):
            self.auth_service_url += "/"
        self.validation_url = f"{self.auth_service_url}api/check-token/"
        self.timeout = 10.0

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        if not request.url.path.startswith(self.include_path_start):
            return await call_next(request)

        if request.url.path.startswith("/api/v1/health"):
            return await call_next(request)

        auth_header = request.headers.get("authorization")
        if not auth_header:
            logger.warning("token_missing_authorization_header")
            return JSONResponse(status_code=401, content={"detail": "Token is required"})

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = auth_header
            
        if not token:
            logger.warning("token_missing_bearer_value")
            return JSONResponse(status_code=401, content={"detail": "Token is required"})

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.validation_url,
                    params={"token": token},
                    timeout=self.timeout
                )
                
                logger.info(f"status={response.status_code} | url={self.validation_url}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"valid={data.get('valid')} | data={data}")
                    if not data.get("valid", False):
                        logger.warning(f"token_invalid | url={self.validation_url}")
                        return JSONResponse(status_code=401, content={"detail": "Invalid token"})
                else:
                    logger.warning(f"token_validation_failed | status={response.status_code} | response={response.text}")
                    return JSONResponse(status_code=401, content={"detail": "Token validation failed"})
                    
        except httpx.RequestError as e:
            logger.warning(f"token_validation_request_error | url={self.validation_url} | error={e}")
            return JSONResponse(status_code=401, content={"detail": "Token validation failed"})
        except Exception as e:
            logger.error(f"token_validation_unexpected_error | error={e}")
            return JSONResponse(status_code=401, content={"detail": "Token validation failed"})

        return await call_next(request)
