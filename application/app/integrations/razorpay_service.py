"""
Razorpay service for handling payment operations in the OMS system.

This module provides the main interface for Razorpay payment gateway integration,
including order creation, payment verification, and webhook handling.
"""

import razorpay
import hashlib
import hmac
import json
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timezone
from app.models.common import get_ist_now

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("razorpay_service")

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()


class RazorpayService:
    """Service class for Razorpay payment operations"""
    
    def __init__(self):
        self.key_id = configs.RAZORPAY_KEY_ID
        self.key_secret = configs.RAZORPAY_KEY_SECRET
        self.webhook_secret = configs.RAZORPAY_WEBHOOK_SECRET
        self.integration_enabled = configs.RAZORPAY_INTEGRATION_ENABLED
        self.base_url = configs.RAZORPAY_BASE_URL
        self.currency = configs.RAZORPAY_CURRENCY
        self.timeout = configs.RAZORPAY_TIMEOUT

        if not self.integration_enabled:
            logger.error("Razorpay integration is disabled")
            raise ValueError("Razorpay integration is disabled")

        if not self.key_id or not self.key_secret or not self.webhook_secret:
            logger.error("Razorpay key ID, key secret, and webhook secret are required")
            raise ValueError("Razorpay key ID, key secret, and webhook secret are required")

        # Initialize Razorpay client
        self.client = None
        try:
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
            logger.info(f"razorpay_client_initialized | key_id={self.key_id}")
        except Exception as e:
            logger.error(f"razorpay_client_init_error | error={e}", exc_info=True)
            raise ValueError(f"Failed to initialize Razorpay client: {e}")

    async def create_razorpay_order(self, order_id: str, amount: Decimal, customer_details: Dict[str, Any], notes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a Razorpay order for payment processing
        Args:
            order_id: OMS order ID
            amount: Order amount in rupees
            customer_details: Customer information
            notes: Additional notes for the order
        Returns:
            Dict containing Razorpay order details or error info
        """
        if not self.integration_enabled:
            logger.info(f"razorpay_order_create_skipped | order_id={order_id} amount={amount}")
            return {
                "success": False,
                "skipped": True,
                "message": "Razorpay integration is disabled"
            }

        try:
            # Convert amount to paise (Razorpay expects amount in smallest currency unit)
            logger.info(f"amount_to_paise | amount={amount} and type of amount={type(amount)}")
            amount_paise = int(amount * 100)
            logger.info(f"amount_to_paise | amount_paise={amount_paise} and type of amount_paise={type(amount_paise)}")

            # Prepare order data
            order_data = {
                "amount": amount_paise,
                "currency": self.currency,
                "receipt": order_id,
                "notes": notes or {}
            }

            # Add customer details to notes
            order_data["notes"].update({
                "oms_order_id": order_id,
                "customer_id": customer_details.get("customer_id", ""),
                "customer_name": customer_details.get("customer_name", ""),
                "created_at": datetime.now(timezone.utc).isoformat()
            })

            # Create order in Razorpay
            razorpay_order = self.client.order.create(data=order_data)
            logger.info(f"razorpay_order_created | order_id={order_id} razorpay_order_id={razorpay_order.get('id')} amount_paise={amount_paise} currency={self.currency}")
            
            # Convert Unix timestamp to readable format
            from app.utils.datetime_helpers import format_datetime_readable
            created_timestamp = razorpay_order["created_at"]

            # Debug: Log the actual timestamp value
            logger.info(f"razorpay_timestamp_debug | timestamp={created_timestamp} timestamp_type={type(created_timestamp)}")

            # Use current IST time instead of Razorpay timestamp for consistency
            created_readable = format_datetime_readable(get_ist_now())

            return {
                "success": True,
                "razorpay_order_id": razorpay_order["id"],
                "amount": amount,
                "amount_paise": amount_paise,
                "currency": razorpay_order["currency"],
                "status": razorpay_order["status"],
                "key_id": self.key_id,
                "created_at": created_readable
            }

        except Exception as e:
            logger.error(f"razorpay_order_create_error | order_id={order_id} amount={amount} error={e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create Razorpay order"
            }

    async def verify_payment_signature(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        """
        Verify Razorpay payment signature for security

        Args:
            razorpay_order_id: Razorpay order ID
            razorpay_payment_id: Razorpay payment ID
            razorpay_signature: Signature to verify

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.integration_enabled:
            logger.warning(f"razorpay_signature_verify_skipped | razorpay_order_id={razorpay_order_id}")
            return False

        try:
            # Create signature string
            signature_string = f"{razorpay_order_id}|{razorpay_payment_id}"

            # Generate expected signature
            expected_signature = hmac.new(self.key_secret.encode(), signature_string.encode(), hashlib.sha256).hexdigest()

            # Compare signatures
            is_valid = hmac.compare_digest(expected_signature, razorpay_signature)
            if is_valid:
                logger.info(f"razorpay_signature_verified | razorpay_order_id={razorpay_order_id} razorpay_payment_id={razorpay_payment_id}")
            else:
                logger.warning(f"razorpay_signature_invalid | razorpay_order_id={razorpay_order_id} razorpay_payment_id={razorpay_payment_id}")

            return is_valid

        except Exception as e:
            logger.error(f"razorpay_signature_verify_error | razorpay_order_id={razorpay_order_id} razorpay_payment_id={razorpay_payment_id} error={e}", exc_info=True)
            return False

    async def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """
        Verify webhook signature from Razorpay
        Args:
            payload: Webhook payload
            signature: Webhook signature
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.integration_enabled:
            logger.warning("razorpay_webhook_verify_skipped")
            return False
        try:
            expected_signature = hmac.new(self.webhook_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"razorpay_webhook_verify_error | error={e}", exc_info=True)
            return False

    async def get_payment_details(self, payment_id: str) -> Dict[str, Any]:
        """
        Fetch payment details from Razorpay
        Args:
            payment_id: Razorpay payment ID
        Returns:
            Payment details or error info
        """
        if not self.integration_enabled:
            logger.warning(f"razorpay_payment_details_skipped | payment_id={payment_id}")
            return {
                "success": False,
                "skipped": True,
                "message": "Razorpay integration is disabled"
            }
        try:
            payment = self.client.payment.fetch(payment_id)
            return {
                "success": True,
                "payment": payment
            }

        except Exception as e:
            logger.error(f"razorpay_payment_details_error | payment_id={payment_id} error={e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to fetch payment details"
            }


# Global service instance
razorpay_service = RazorpayService()
