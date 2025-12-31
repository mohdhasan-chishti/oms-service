"""
Transaction Lock Middleware for Order Creation

Prevents duplicate order creation by hashing request payload and storing in Redis with TTL.
Returns 409 Conflict if same payload is received within the lock window.
"""

import json
import hashlib
from typing import Callable
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.connections.redis_wrapper import RedisJSONWrapper
from app.config.settings import OMSConfigs
from app.logging.utils import get_app_logger

logger = get_app_logger("transaction_lock_middleware")
configs = OMSConfigs()


class TransactionLockMiddleware(BaseHTTPMiddleware):
    """
    Middleware to prevent duplicate order creation requests.

    Uses payload hashing and Redis to detect duplicate requests within a TTL window.
    Only applies to order creation endpoints.
    """

    def __init__(self, app):
        super().__init__(app)
        self.lock_ttl = configs.TRANSACTION_LOCK_TTL_SECONDS
        self.biller_customer_lock_ttl = configs.BILLER_CUSTOMER_LOCK_TTL_SECONDS

        # Endpoints to apply transaction lock
        self.protected_endpoints = [
            "/app/v1/create_order",
            "/pos/v1/create_order",
            "/api/v1/create_order",
        ]

        logger.info(f"TransactionLockMiddleware initialized with TTL={self.lock_ttl}s, Biller-Customer TTL={self.biller_customer_lock_ttl}s")

    def should_apply_lock(self, request: Request) -> bool:
        """Check if transaction lock should be applied to this request."""
        path = request.url.path
        method = request.method

        # Only apply to POST requests on protected endpoints
        if method != "POST":
            return False

        return any(path.endswith(endpoint) for endpoint in self.protected_endpoints)

    def generate_payload_hash(self, body: bytes) -> str:
        """
        Generate SHA256 hash of request payload.
        Removes dynamic fields that shouldn't affect duplicate detection.

        Args:
            body: Raw request body bytes

        Returns:
            Hexadecimal hash string
        """
        try:
            # Parse JSON payload
            payload = json.loads(body.decode('utf-8'))
            dynamic_fields = ['eta','eta_data']
            for field in dynamic_fields:
                if field in payload:
                    payload.pop(field)

            normalized_payload = json.dumps(payload, sort_keys=True)
            return hashlib.sha256(normalized_payload.encode('utf-8')).hexdigest()

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to parse payload for normalization: {e}")
            return hashlib.sha256(body).hexdigest()

    def generate_biller_customer_lock_key(self, body: bytes, request: Request) -> str:
        """
        Generate lock key based on biller_id and customer_id combination.
        This prevents same biller from creating multiple orders for same customer within TTL.

        Args:
            body: Raw request body bytes
            request: FastAPI request object

        Returns:
            Lock key string or None if not applicable
        """
        try:
            # Extract biller_id from request state (set by auth middleware)
            biller_id = getattr(request.state, "user_id", None)
            if not biller_id:
                logger.warning(f"No biller ID found in request")
                return None

            # Extract customer_id from request payload
            payload = json.loads(body.decode('utf-8'))
            customer_id = payload.get("customer_id")
            logger.info(f"Checking order creation for biller: {biller_id}, customer: {customer_id}")
            
            if not customer_id:
                logger.warning(f"No customer ID found in request payload")
                return None

            # Create unique key for this biller-customer combination
            lock_key = f"biller_customer_lock:{biller_id}:{customer_id}"
            return lock_key

        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
            logger.warning(f"Failed to generate biller-customer lock key: {e}")
            return None

    def try_acquire_lock(self, lock_key: str, payload_hash: str, request: Request, ttl: int = None) -> bool:
        """
        Atomically try to acquire lock in Redis using SETNX.
        Creates a fresh Redis connection for each request to ensure connection status is current.

        Args:
            lock_key: Redis key for the lock
            payload_hash: Hash of the request payload
            request: FastAPI request object
            ttl: Time-to-live in seconds (defaults to self.lock_ttl)

        Returns:
            True if lock was acquired (request can proceed)
            False if lock already exists (duplicate request)
        """
        try:
            # Use provided TTL or default
            lock_ttl = ttl if ttl is not None else self.lock_ttl
            
            # Create fresh Redis connection to check current status
            redis_client = RedisJSONWrapper(database=configs.REDIS_CACHE_DB)
            if not redis_client.connected:
                logger.error("Redis not connected, allowing request (fail-open)")
                return True

            lock_data = {
                "payload_hash": payload_hash,
                "endpoint": request.url.path,
                "client_ip": request.client.host,
                "user_agent": request.headers.get("user-agent", "unknown"),
                "timestamp": str(request.state.__dict__.get("request_timestamp", ""))
            }

            # Atomic check-and-set: only set if key doesn't exist
            acquired = redis_client.set_if_not_exists_with_ttl(lock_key, lock_data, lock_ttl)
            if acquired:
                logger.info(f"Transaction lock acquired | key={lock_key} | hash={payload_hash[:16]}... | ttl={lock_ttl}s")
            else:
                logger.warning(f"Transaction lock already exists | key={lock_key} | hash={payload_hash[:16]}...")

            return acquired

        except Exception as e:
            logger.error(f"Error acquiring lock in Redis: {e}")
            return True

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Intercept requests and apply transaction lock for order creation endpoints.
        """
        # Check if this endpoint needs transaction lock
        if not self.should_apply_lock(request):
            return await call_next(request)

        # Read request body
        body = await request.body()

        # Check 1: Biller-Customer lock (for POS orders only)
        # Prevents same biller from creating multiple orders for same customer within TTL
        biller_customer_lock_key = self.generate_biller_customer_lock_key(body, request)
        if biller_customer_lock_key and request.url.path.endswith("/pos/v1/create_order"):
            biller_customer_lock_acquired = self.try_acquire_lock(biller_customer_lock_key, "biller_customer_lock", request, self.biller_customer_lock_ttl)
            if not biller_customer_lock_acquired:
                logger.warning(f"Duplicate order creation attempt detected for this customer | endpoint={request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    content={
                        "success": False,
                        "error": "DUPLICATE_BILLER_CUSTOMER_REQUEST",
                        "message": f"Duplicate order creation request detected for this customer. Please wait {self.biller_customer_lock_ttl} seconds before retrying.",
                        "retry_after_seconds": self.biller_customer_lock_ttl
                    }
                )
        else:
            logger.info(f"Skipping biller-customer check - missing required information")

        # Check 2: Payload hash lock (prevents duplicate order content)
        payload_hash = self.generate_payload_hash(body)
        lock_key = f"transaction_lock:{payload_hash}"

        # Atomically try to acquire lock (check-and-set in single operation)
        lock_acquired = self.try_acquire_lock(lock_key, payload_hash, request)

        if not lock_acquired:
            # Lock already exists - duplicate request detected
            logger.warning(f"Duplicate order creation attempt detected | endpoint={request.url.path} | hash={payload_hash[:16]}... | client_ip={request.client.host}")
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "success": False,
                    "error": "DUPLICATE_REQUEST",
                    "message": f"Duplicate order creation request detected. Please wait {self.lock_ttl} seconds before retrying.",
                    "retry_after_seconds": self.lock_ttl
                }
            )

        # Process request
        try:
            # Restore body for downstream processing
            async def receive():
                return {"type": "http.request", "body": body}

            request._receive = receive
            response = await call_next(request)

            logger.info(f"Order creation request processed | endpoint={request.url.path} | hash={payload_hash[:16]}... | status={response.status_code}")

            return response

        except Exception as e:
            logger.error(f"Error processing order creation request: {e}")
            raise
