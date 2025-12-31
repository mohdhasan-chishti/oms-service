"""
Razorpay webhook routes for payment status updates.

This module handles webhook notifications from Razorpay payment gateway
for updating payment status in the OMS system.
"""

import json
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Header
from fastapi.responses import JSONResponse

from app.integrations.razorpay_service import razorpay_service
from app.services.payment_service import PaymentService
from app.core.constants import PaymentStatus

# Request context
from app.middlewares.request_context import request_context

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger(__name__)

# Create router for webhook endpoints
webhook_router = APIRouter(prefix="", tags=["webhooks"])


@webhook_router.post("/razorpay_webhook")
async def razorpay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature")
):
    """
    Handle Razorpay webhooks for payment status updates.
    
    This endpoint receives webhook notifications from Razorpay
    and updates payment status accordingly.
    """
    try:
        request_context.module_name = 'route_webhook_razorpay'
        # Get raw payload
        payload = await request.body()
        payload_str = payload.decode('utf-8')

        # Verify webhook signature
        if not x_razorpay_signature:
            logger.warning("webhook_missing_signature | reason=missing_signature")
            raise HTTPException(status_code=400, detail="Missing signature")

        is_verified = await razorpay_service.verify_webhook_signature(
            payload_str,
            x_razorpay_signature
        )

        if not is_verified:
            logger.warning("webhook_invalid_signature | reason=signature_mismatch")
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Parse webhook payload
        webhook_data = json.loads(payload_str)
        event = webhook_data.get("event")
        entity = webhook_data.get("payload", {}).get("payment", {}).get("entity", {})

        logger.info(f"webhook_received | event={event}")

        # Handle payment events
        if event in ["payment.captured", "payment.failed", "payment.authorized"]:
            order_id = entity.get("notes", {}).get("oms_order_id")
            payment_id = entity.get("id")
            razorpay_status = entity.get("status")
            payment_amount = float(entity.get("amount", 0)) / 100  # Convert from paise

            if order_id and payment_id:
                # Map Razorpay status to our payment status
                if razorpay_status == "captured":
                    payment_status = PaymentStatus.COMPLETED
                elif razorpay_status == "failed":
                    payment_status = PaymentStatus.FAILED
                else:
                    payment_status = PaymentStatus.PENDING
                
                # Update payment status and check order completion
                payment_service = PaymentService()
                
                # Update payment status
                background_tasks.add_task(
                    payment_service.update_payment_status,
                    payment_id,
                    payment_status
                )
                
                # If payment is successful, check if order can be completed
                if payment_status == PaymentStatus.COMPLETED:
                    background_tasks.add_task(
                        payment_service.check_and_complete_order_if_all_payments_successful,
                        int(order_id)
                    )

                logger.info(f"Webhook processed for order {order_id}, payment {payment_id}")
            else:
                logger.warning(f"webhook_missing_fields | reason=missing_order_or_payment_id entity_keys={list(entity.keys())}")

        return JSONResponse(content={"status": "ok"})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"webhook_processing_error | error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
