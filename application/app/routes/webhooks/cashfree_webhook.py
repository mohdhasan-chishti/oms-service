"""
Cashfree webhook routes for OMS service.
Handles payment webhooks at /cashfree/webhook path.
"""

import json
import traceback
import hmac
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from typing import Optional
from app.core.constants import PaymentStatus, OrderStatus

# Repository and database
from app.repository.payments import PaymentRepository
from app.connections.database import execute_raw_sql
from app.services.payments.payment_processor import OrderPaymentProcessor
from app.services.order_service import OrderService
from app.integrations.potions_service import PotionsService
from app.config.settings import OMSConfigs

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger('cashfree_webhook-payments')

# Create router for Cashfree webhook
cashfree_webhook_router = APIRouter(prefix="", tags=["cashfree-webhook"])

def verify_signature(raw_body: bytes, signature: str, timestamp: str) -> bool:
    configs = OMSConfigs()
    secret = getattr(configs, 'CASHFREE_WEBHOOK_SECRET', '')
    if not secret:
        logger.error("Cashfree webhook: CASHFREE_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    if not timestamp:
        logger.error("Cashfree webhook: missing timestamp")
        return False
    signed_payload = timestamp.encode() + raw_body
    computed = base64.b64encode(hmac.new(secret.encode('utf-8'), signed_payload, hashlib.sha256).digest()).decode('utf-8')
    return hmac.compare_digest(computed, signature)

@cashfree_webhook_router.post("/webhook")
async def cashfree_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Cashfree payment webhooks for payment status updates.
    """
    try:
        # Read raw body for signature verification
        raw_body = await request.body()
        signature = request.headers.get('x-webhook-signature')
        timestamp = request.headers.get('x-webhook-timestamp')

        if not signature:
            logger.error("Cashfree webhook: missing x-webhook-signature header")
            raise HTTPException(status_code=400, detail="Missing x-webhook-signature header")

        if not verify_signature(raw_body, signature, timestamp):
            logger.error("Cashfree webhook: invalid signature")
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Parse webhook data only after successful verification
        webhook_data = json.loads(raw_body.decode('utf-8'))
        event_type = webhook_data.get("type")  # cashfree sends 'type'
        
        logger.info(f"Cashfree webhook received | event={event_type}")
        
        
        # Process only payment events
        if event_type and event_type in ("PAYMENT_SUCCESS_WEBHOOK", "PAYMENT_FAILED_WEBHOOK"):
            # Process with background sync tasks
            await process_cashfree_webhook(webhook_data, background_tasks)
            
            return {"status": "success", "message": "Webhook processed successfully"}
            
        return {"status": "ignored", "message": "Non-payment event"}
        
    except json.JSONDecodeError:
        logger.error("Cashfree webhook: invalid JSON payload")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except HTTPException as he:
        # Propagate HTTP errors (e.g., 400 invalid signature) without converting to 500
        raise he
    except Exception as e:
        logger.error(f"Cashfree webhook error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_cashfree_webhook(webhook_data: dict, background_tasks: BackgroundTasks):
    """
    Process Cashfree webhook data and update payment status
    """
    try:
        payment_data = webhook_data.get("data", {})
        
        # Extract data
        cf_payment_id = payment_data.get("payment", {}).get("cf_payment_id")
        payment_status = payment_data.get("payment", {}).get("payment_status")
        gateway_order_id = payment_data.get("order", {}).get("order_id")  # Cashfree's gateway order ID

        if not all([gateway_order_id, cf_payment_id, payment_status]):
            logger.error(f"Incomplete webhook data: {webhook_data}")
            return

        logger.info(f"Cashfree webhook received | gateway_order_id={gateway_order_id} | cf_payment_id={cf_payment_id} | status={payment_status}")
        
        # Map to internal status
        if payment_status == "SUCCESS":
            internal_payment_status = PaymentStatus.COMPLETED
        elif payment_status == "FAILED":
            internal_payment_status = PaymentStatus.FAILED
        else:
            internal_payment_status = None
        
        # Skip payments that don't have gateway_order_id
        if not gateway_order_id:
            logger.warning(f"Cashfree webhook: Missing gateway_order_id - skipping | cf_payment_id={cf_payment_id}")
            return
        
        if internal_payment_status:
            logger.info(f"Cashfree webhook: Processing payment | cf_payment_id={cf_payment_id} gateway_order_id={gateway_order_id} status={internal_payment_status}")

            # Initialize repositories and services
            payment_repository = PaymentRepository()
            payment_processor = OrderPaymentProcessor()
            service = OrderService()
            potions_service = PotionsService()
            
            # Fetch all orders by payment_order_id (gateway_order_id)
            orders_to_process = payment_repository.get_orders_by_payment_order_id(gateway_order_id)
            
            if not orders_to_process:
                logger.warning(f"Cashfree webhook: No orders found for gateway_order_id={gateway_order_id}")
                return
            
            logger.info(f"Cashfree webhook: Processing orders | gateway_order_id={gateway_order_id} orders_count={len(orders_to_process)}")
            
            # Process all orders
            for order_data in orders_to_process:
                order_id = order_data.get('order_id')
                facility_name = order_data.get('facility_name')
                order_status = order_data.get('status')
                
                # Only process orders in DRAFT (0) or OPEN (10) status
                if order_status not in [0, 10]:
                    logger.info(f"Cashfree webhook: Skipping order | order_id={order_id} status={order_status}")
                    continue
                
                # Fetch payment records for this order
                payment_records = payment_repository.get_payments_for_order(order_id)
                if not payment_records:
                    logger.warning(f"Cashfree webhook: No payment records | order_id={order_id}")
                    continue
                
                # Find Cashfree payment to validate it exists
                cashfree_payment = None
                for payment_record in payment_records:
                    if payment_record.get("payment_mode", "").lower() == "cashfree":
                        cashfree_payment = payment_record
                        break
                
                if not cashfree_payment:
                    logger.warning(f"Cashfree webhook: No Cashfree payment found | order_id={order_id}")
                    continue
                
                # Process payments for this order
                payments_status, sync_order = await payment_processor.process_razorpay_included_order_payment(order_id, payment_records, cf_payment_id, internal_payment_status)
                
                if payments_status:
                    # Update order status to OPEN
                    order_result = await service.update_order_status(order_id, OrderStatus.OPEN)
                    logger.info(f"Cashfree webhook: Order status updated | order_id={order_id} status={int(OrderStatus.OPEN)} result={order_result}")

                    if sync_order:
                        background_tasks.add_task(potions_service.sync_order_by_id, facility_name, order_id, service)
                        logger.info(f"Cashfree webhook: WMS sync queued | order_id={order_id}")
                else:
                    logger.warning(f"Cashfree webhook: Payment processing failed | order_id={order_id}")

        else:
            logger.error(f"Cashfree webhook: Invalid payment status | cf_payment_id={cf_payment_id} internal_status={internal_payment_status}")
        
    except Exception as e:
        logger.error(f"Error processing Cashfree webhook: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise
