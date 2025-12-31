"""
Order payment processing functions
"""
from typing import Dict, List

from fastapi import HTTPException, BackgroundTasks

from app.services.order_service import OrderService
from app.services.payments.payment_processor import OrderPaymentProcessor
from app.integrations.potions_service import PotionsService
from app.logging.utils import get_app_logger

logger = get_app_logger("app.core.orders_creation.order_processor")


async def process_payments_for_orders(
    created_orders: List[Dict],
    all_payment_records: List[Dict],
    customer_id: str,
    background_tasks: BackgroundTasks
):
    """
    Process payments for all orders
    """
    payment_processor = OrderPaymentProcessor()
    potions_service = PotionsService()
    service = OrderService()

    for order_data in created_orders:
        # Get payment records for this order
        order_payment_records = []
        for payment_record in all_payment_records:
            if payment_record['order_id'] == order_data['internal_order_id']:
                order_payment_records.append(payment_record)
        
        if order_payment_records:
            payments_status, sync_order = await payment_processor.process_order_payment(
                order_data['order_id'],
                order_payment_records,
                customer_id
            )
            
            if not payments_status:
                raise HTTPException(status_code=400, detail="Failed to process order payment")
            
            # Sync to Potions if needed
            if sync_order:
                background_tasks.add_task(potions_service.sync_order_by_id, order_data['facility_name'], order_data['order_id'], service)
    
    logger.info(f"Processed payments for {len(created_orders)} orders")
