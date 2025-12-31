"""
Token validation middleware and decorators for API authentication
"""
import httpx
import os
from typing import Dict, Any, Callable
from functools import wraps
from fastapi import HTTPException, Request

from app.middlewares.request_context import request_context

# Logger 
from app.logging.utils import get_app_logger
logger = get_app_logger('token_validation')

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()
TOKEN_VALIDATION_URL = configs.TOKEN_VALIDATION_URL


class TokenValidationService:
    """Service for validating tokens against external API"""
    
    def __init__(self, validation_url: str = None):
        if validation_url is None:
            validation_url = TOKEN_VALIDATION_URL
        
        if validation_url and not validation_url.endswith("/api/check-token/"):
            validation_url = validation_url.rstrip("/")
            if not validation_url.endswith("/api/check-token"):
                validation_url += "/api/check-token/"
            else:
                validation_url += "/"
        
        self.validation_url = validation_url
    
    async def validate_token(self, token: str) -> bool:
        """Validate token against external API"""
        request_context.module_name = 'middleware_token_validation'
        logger.info(f"token_validation_started | validation_url={self.validation_url}")
        logger.info(f"token_received | token_prefix={token[:10] if token else None}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.validation_url,
                    params={"token": token},
                    timeout=10.0
                )
                
                logger.info(f"token_validation_response | status_code={response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    is_valid = data.get("valid", False)
                    logger.info(f"token_validation_result | valid={is_valid}")
                    return is_valid
                else:
                    logger.warning(f"token_validation_failed | status_code={response.status_code}")
                    return False
                    
        except httpx.RequestError as e:
            logger.error(f"token_validation_request_error | error={e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"token_validation_unexpected_error | error={e}", exc_info=True)
            return False


def require_token_validation(func: Callable) -> Callable:
    """
    Decorator for endpoints that require 3PL token validation
    Extracts token from query parameters or request body
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract token from function arguments
        token = None
        
        # Check if token is in kwargs (query parameters)
        if 'token' in kwargs:
            token = kwargs['token']
        else:
            # Check if there's a request object with token in body
            for arg in args:
                if hasattr(arg, 'token'):
                    token = arg.token
                    break
        
        if not token:
            raise HTTPException(status_code=401, detail="Token is required")
        
        # Validate token
        token_service = TokenValidationService()
        is_valid = await token_service.validate_token(token)
        
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Call the original function
        return await func(*args, **kwargs)
    
    return wrapper
