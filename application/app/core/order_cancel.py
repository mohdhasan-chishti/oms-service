import logging
from typing import List, Dict
from fastapi import HTTPException
from app.connections.database import get_raw_transaction
from app.integrations.potions_service import PotionsService
from app.core.constants import OrderStatus, CancelReasons
from sqlalchemy import text

from app.utils.order_utils import can_cancel_order

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger("app.core.order_cancel")


def get_cancel_reasons_core() -> Dict[str, Dict[str, str]]:
    """
    Returns predefined cancel reasons for orders as key-value pairs.
    Returns:
        Dict with 'reasons' key containing dict of cancellation reasons where key is code and value is display name
    """
    return {"reasons": CancelReasons.get_all_reasons()}


async def cancel_order_core(order_id: str, cancel_reason: str = None, cancel_remarks: str = None):
    try:
        with get_raw_transaction() as conn:
            check_order_sql = """
                SELECT id, order_id, status, facility_name, marketplace
                FROM orders 
                WHERE order_id = :order_id
            """
            
            result = conn.execute(text(check_order_sql), {'order_id': order_id})
            order_row = result.fetchone()
            
            if not order_row:
                logger.warning(f"Order {order_id} not found in database")
                raise HTTPException(
                    status_code=404, 
                    detail=f"Order {order_id} not found"
                )
            
            current_status = order_row.status
            facility_name = order_row.facility_name
            marketplace = order_row.marketplace

            # Check if order is already cancelled
            if current_status == OrderStatus.CANCELED:
                logger.info(f"Order {order_id} is already cancelled, no action needed")
                return {
                    "success": True,
                    "message": f"Order {order_id} is already cancelled",
                    "order_id": order_id,
                    "status": OrderStatus.get_customer_status_name(OrderStatus.CANCELED)
                }

            # Check if order is cancelable
            is_cancelable = can_cancel_order(current_status, marketplace)
            if not is_cancelable:
                logger.warning(f"Order {order_id} cannot be cancelled due to status: {current_status}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Order {order_id} cannot be cancelled. Current status: {current_status}"
                )

            # Update order status
            update_order_sql = """
                UPDATE orders 
                SET status = :status, updated_at = NOW(), remarks = 'USER_CANCELLED',
                    cancel_reason = :cancel_reason, cancel_remarks = :cancel_remarks
                WHERE order_id = :order_id
            """

            conn.execute(text(update_order_sql), {
                'status': OrderStatus.CANCELED,
                'order_id': order_id,
                'cancel_reason': cancel_reason,
                'cancel_remarks': cancel_remarks
            })

            # Update order items status
            update_items_sql = """
                UPDATE order_items 
                SET status = :status, cancelled_quantity = quantity, updated_at = NOW()
                WHERE order_id = :order_pk
            """

            conn.execute(text(update_items_sql), {
                'status': OrderStatus.CANCELED,
                'order_pk': order_row.id
            })

            conn.commit()
            logger.info(f"Order {order_id} status updated to CANCELED in database")
        
        try:
            potions_service = PotionsService()
            wms_result = await potions_service.cancel_outbound_order(
                order_reference=order_id,
                warehouse=facility_name
            )

            if wms_result.success:
                logger.info(f"Order {order_id} successfully cancelled in WMS")
                wms_message = "Order cancelled in WMS and stock updated"
            else:
                logger.warning(f"WMS cancellation failed for order {order_id}: {wms_result.message}")
                wms_message = f"Order cancelled in OMS but WMS cancellation failed: {wms_result.message}"

        except Exception as wms_error:
            logger.error(f"WMS cancellation error for order {order_id}: {str(wms_error)}")
            wms_message = f"Order cancelled in OMS but WMS cancellation failed: {str(wms_error)}"

        return {
            "success": True,
            "message": f"Order {order_id} cancelled successfully",
            "order_id": order_id,
            "status": OrderStatus.get_customer_status_name(OrderStatus.CANCELED),
            "wms_status": wms_message
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error cancelling order {order_id}: {exc}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error while cancelling order: {str(exc)}"
        ) from exc
