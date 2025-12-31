"""
Razorpay webhook routes for OMS service.
Handles payment webhooks at /razorpay/webhook path.
"""

import json
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from app.integrations.razorpay_service import razorpay_service
from app.integrations.potions_service import PotionsService
from app.core.constants import PaymentStatus

# Repository
from app.repository.payments import PaymentRepository
from app.services.payments.payment_processor import OrderPaymentProcessor
from app.services.order_service import OrderService
from app.core.constants import OrderStatus
# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger('razorpay_webhook-payments')

# Create router for Razorpay webhook
razorpay_webhook_router = APIRouter(prefix="", tags=["razorpay-webhook"])

@razorpay_webhook_router.post("/webhook")
async def razorpay_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Razorpay payment webhooks for payment status updates.
    Processes only payment.captured and payment.failed events.
    """
    # Get raw body for signature verification
    raw_body = await request.body()
    signature = request.headers.get('X-Razorpay-Signature')

    if not signature:
        logger.warning("OMS webhook: missing X-Razorpay-Signature header")
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header")

    try:
        # Verify webhook signature
        is_verified = await razorpay_service.verify_webhook_signature(raw_body.decode('utf-8'), signature)
        if not is_verified:
            logger.warning("OMS webhook: invalid signature")
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Parse webhook data
        webhook_data = json.loads(raw_body.decode('utf-8'))
        event = webhook_data.get("event")
        logger.info(f"OMS webhook received | event={event}")

        # OMS only handles payment events
        if event in ["payment.captured", "payment.failed"]:
            payment_entity = webhook_data.get("payload", {}).get("payment", {}).get("entity", {})
            payment_id = payment_entity.get("id")
            payment_status = payment_entity.get("status")
            razorpay_order_id = payment_entity.get("order_id")

            if payment_status == "captured":
                internal_payment_status = PaymentStatus.COMPLETED
            elif payment_status == "failed":
                internal_payment_status = PaymentStatus.FAILED
            else:
                internal_payment_status = None
            
            # Skip payments that don't have order_id
            if not razorpay_order_id:
                logger.warning(f"OMS webhook: Missing razorpay order_id - skipping | payment_id={payment_id}")
                return {"status": "ok", "event": event}
            
            if internal_payment_status:
                logger.info(f"OMS webhook: Processing payment | payment_id={payment_id} razorpay_order_id={razorpay_order_id} status={internal_payment_status}")

                # Initialize repositories and services
                payment_repository = PaymentRepository()
                payment_processor = OrderPaymentProcessor()
                service = OrderService()
                potions_service = PotionsService()
                
                # Fetch all orders by payment_order_id (razorpay_order_id)
                orders_to_process = payment_repository.get_orders_by_payment_order_id(razorpay_order_id)
                
                if not orders_to_process:
                    logger.warning(f"OMS webhook: No orders found for razorpay_order_id={razorpay_order_id}")
                    return {"status": "ok", "event": event}
                
                logger.info(f"OMS webhook: Processing orders | razorpay_order_id={razorpay_order_id} orders_count={len(orders_to_process)}")
                
                # Process all orders
                for order_data in orders_to_process:
                    order_id = order_data.get('order_id')
                    facility_name = order_data.get('facility_name')
                    order_status = order_data.get('status')
                    
                    # Only process orders in DRAFT (0) or OPEN (10) status
                    if order_status not in [0, 10]:
                        logger.info(f"OMS webhook: Skipping order | order_id={order_id} status={order_status}")
                        continue
                    
                    # Fetch payment records for this order
                    payment_records = payment_repository.get_payments_for_order(order_id)
                    if not payment_records:
                        logger.warning(f"OMS webhook: No payment records | order_id={order_id}")
                        continue
                    
                    # Process payments for this order
                    payments_status, sync_order = await payment_processor.process_razorpay_included_order_payment(order_id, payment_records, payment_id, internal_payment_status)
                    
                    if payments_status:
                        # Update order status to OPEN
                        order_result = await service.update_order_status(order_id, OrderStatus.OPEN)
                        logger.info(f"order_status_update_post_payment | order_id={order_id} status={int(OrderStatus.OPEN)} result={order_result}")
                        
                        if sync_order:
                            background_tasks.add_task(potions_service.sync_order_by_id, facility_name, order_id, service)
                            logger.info(f"OMS webhook: WMS sync queued | order_id={order_id}")
                    else:
                        logger.warning(f"OMS webhook: Payment processing failed | order_id={order_id}")

            else:
                logger.error(f"OMS webhook: Invalid payment status | payment_id={payment_id} internal_status={internal_payment_status}")

        return {"status": "ok", "event": event}

    except Exception as e:
        logger.error(f"OMS webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
