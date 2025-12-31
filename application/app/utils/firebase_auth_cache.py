"""Utility helpers for caching Firebase Auth token verification results."""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional

from firebase_admin import auth

from app.connections.redis_wrapper import RedisJSONWrapper
from app.config.settings import OMSConfigs
from app.logging.utils import get_app_logger

configs = OMSConfigs()
logger = get_app_logger("firebase_auth_cache")

CACHE_ENABLED = configs.FIREBASE_AUTH_CACHE_ENABLED
CACHE_TTL_DEFAULT = configs.FIREBASE_AUTH_CACHE_TTL_SECONDS
CACHE_PREFIX = configs.FIREBASE_AUTH_CACHE_PREFIX


def build_cache_key(token: str, prefix: Optional[str] = CACHE_PREFIX) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"

def determine_ttl(decoded_token: Dict[str, Any]) -> int:
    exp = decoded_token.get("exp")
    if not isinstance(exp, (int, float)):
        return CACHE_TTL_DEFAULT

    remaining = int(exp) - int(time.time())
    if remaining <= 0:
        return 0

    if CACHE_TTL_DEFAULT > 0:
        return min(remaining, CACHE_TTL_DEFAULT)
    return remaining


def extract_bearer_token(header_value: Optional[str]) -> Optional[str]:
    if not header_value:
        return None

    header = header_value.strip()
    if not header:
        return None

    if len(header) >= 7 and header[:7].lower() == "bearer ":
        return header[7:].strip() or None
    return header


def verify_id_token_with_cache(token: str, app_instance, cache_prefix: str = CACHE_PREFIX) -> Dict[str, Any]:
    """Verify Firebase ID token using Redis-backed caching when available."""
    if not token:
        raise ValueError("Token cannot be empty for verification")

    cache_key = None
    redis_cache_client: Optional[RedisJSONWrapper] = None

    if CACHE_ENABLED:
        redis_instance = RedisJSONWrapper(database=configs.REDIS_CACHE_DB)
        if getattr(redis_instance, "connected", False):
            redis_cache_client = redis_instance
        else:
            logger.warning("Redis cache for Firebase auth is disabled due to connection failure")

    if CACHE_ENABLED and redis_cache_client:
        cache_key = build_cache_key(token, prefix=cache_prefix)
        cached = redis_cache_client.get(cache_key)
        if cached:
            return cached

    decoded_token = auth.verify_id_token(token, app=app_instance)

    if cache_key and decoded_token and redis_cache_client:
        ttl = determine_ttl(decoded_token)
        if ttl > 0:
            try:
                redis_cache_client.set_with_ttl(cache_key, decoded_token, ttl)
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("Failed to cache Firebase token verification: %s", exc)

    return decoded_token
