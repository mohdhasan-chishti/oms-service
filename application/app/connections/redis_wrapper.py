import json
import redis
import os
from urllib.parse import quote_plus

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("redis_wrapper")

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()

REDIS_URL = configs.REDIS_URL

class RedisKeyProcessor:
    def __init__(self):
        pass

    @staticmethod
    def _safe(part: str) -> str:
        """Encode dynamic key segments so Redis keys contain only URL-safe chars."""
        return quote_plus(str(part), safe='')

    def _stock_key(self, warehouse_name, sku_code: str | None = None):
        """Return the Redis key for a given warehouse / SKU.

        When *sku_code* is provided we return the concrete key
        ``stock:{warehouse}:{sku}``.
        When it is *None* we return a pattern that matches *all* SKUs in the
        warehouse (``stock:{warehouse}:*``).  The latter is useful for ops such
        as *get_all_stock*.
        """
        wh_enc = self._safe(warehouse_name)
        if sku_code:
            sku_enc = self._safe(sku_code)
            return f"stock:{wh_enc}:{sku_enc}"
        # wildcard pattern for SCAN / KEYS
        return f"stock:{wh_enc}:*"

class RedisJSONWrapper:
    def __init__(self, redis_uri=REDIS_URL, database=None):
        if database is not None:
            redis_uri = f"{redis_uri}/{database}"
        try:
            self.redis_client = redis.from_url(redis_uri)
            self.redis_client.ping()
            self.connected = True
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to connect to Redis at {redis_uri}: {e}")
            self.redis_client = None
            self.connected = False

    def set(self, key, data):
        self.redis_client.set(key, json.dumps(data))

    def set_with_ttl(self, key, data, ttl_seconds: int):
        """Set a key with a TTL (in seconds). Stores data as JSON string.

        Falls back to non-TTL set if ttl_seconds is invalid (<=0).
        """
        try:
            value = json.dumps(data)
            if isinstance(ttl_seconds, int) and ttl_seconds > 0:
                # Use SETEX to ensure expiry is attached atomically with the value
                self.redis_client.setex(key, ttl_seconds, value)
            else:
                self.redis_client.set(key, value)
        except Exception as e:
            logger.error(f"Redis set_with_ttl error for key={key}: {e}")
            # Best-effort fallback
            try:
                self.redis_client.set(key, value)
            except Exception:
                pass

    def set_if_not_exists_with_ttl(self, key, data, ttl_seconds: int) -> bool:
        """
        Atomically set a key with TTL only if it doesn't exist (SETNX behavior).
        Args:
            key: Redis key
            data: Data to store (will be JSON serialized)
            ttl_seconds: TTL in seconds

        Returns:
            True if key was set (didn't exist before)
            False if key already exists (operation failed)
        """
        try:
            value = json.dumps(data)
            result = self.redis_client.set(key, value, nx=True, ex=ttl_seconds)
            return result is not None and result
        except Exception as e:
            logger.error(f"Redis set_if_not_exists_with_ttl error for key={key}: {e}")
            # Fail open - return False to indicate lock acquisition failed
            return False

    def get(self, key):
        data = self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None

    def delete(self, key):
        return self.redis_client.delete(key) > 0

    def keys(self, pattern='*'):
        return [key.decode('utf-8') for key in self.redis_client.keys(pattern)]

    def delete_keys_with_suffix(self, suffix):
        pattern = f"*{suffix}"
        matching_keys = self.keys(pattern)
        for key in matching_keys:
            self.delete(key)
            print(f"Deleted key: {key}")
        return len(matching_keys)
