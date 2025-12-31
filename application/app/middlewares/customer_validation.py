"""
Customer validation middleware for x-customer-key header validation using Firebase.
"""

import json
from fastapi import Request
from fastapi.responses import JSONResponse
from firebase_admin import auth
from starlette.middleware.base import BaseHTTPMiddleware
import firebase_admin
import logging

logger = logging.getLogger(__name__)

# Use the customer Firebase app instance
customer_instance = firebase_admin.get_app("app")  # Assuming customer app uses same instance

class CustomerValidationMiddleware(BaseHTTPMiddleware):
    """Validate x-customer-key header using Firebase for wallet-enabled orders"""

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Skip validation for non-order creation endpoints
        if request.method == "OPTIONS":
            return await call_next(request)

        # Only validate for order creation endpoints that might use wallet
        if not (request.url.path.endswith("/orders") and request.method == "POST"):
            return await call_next(request)

        # Read request body to check for wallet payments
        body = await request.body()
        has_wallet_payment = False
        
        try:
            if body:
                payload = json.loads(body.decode('utf-8'))
                payments = payload.get("payment", [])
                
                # Check if any payment has wallet mode
                has_wallet_payment = any(
                    payment.get("payment_mode") == "wallet" 
                    for payment in payments
                )
        except Exception as e:
            logger.warning(f"Error parsing request body: {e}")

        # Check if x-customer-key header is present
        customer_key = request.headers.get("x-customer-key")
        
        if has_wallet_payment and customer_key:
            try:
                # Validate customer key with Firebase (same as FirebaseAuthMiddlewareAPP)
                decoded_token = auth.verify_id_token(customer_key, app=customer_instance)
                
                # Store customer info in request state for use in order creation
                request.state.customer_validated = True
                request.state.wallet_customer_id = decoded_token.get("user_id")
                logger.info(f"Customer key validated for customer: {decoded_token.get('user_id')}")
                
            except Exception as e:
                logger.warning(f"Invalid customer key provided: {str(e)}")
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Invalid customer key",
                        "message": "Customer validation failed"
                    }
                )
        elif has_wallet_payment and not customer_key:
            logger.warning("customer_key_missing_for_wallet_payment")
            # Wallet payment requires customer key
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Customer key required for wallet payments",
                    "message": "x-customer-key header is required for wallet payment mode"
                }
            )
        else:
            # No wallet payment or valid customer key - proceed
            request.state.customer_validated = True

        return await call_next(request)
