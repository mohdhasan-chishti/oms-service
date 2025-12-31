from fastapi import HTTPException
from app.connections.database import get_db
from app.services.order_service import OrderService
from app.dto.orders import OrderStatusUpdate, OrderItemStatusUpdate  # type: ignore

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger(__name__)

async def update_order_status_core(order_update: OrderStatusUpdate):
    """Shared logic to update status for an order and its items."""
    async with get_db() as db_conn:
        try:
            service = OrderService()
            result = await service.update_order_status(
                order_update.order_id,
                order_update.status,
                db_conn,
            )
            if not result.get("success", False):
                raise HTTPException(status_code=404, detail=result.get("message", "Order not found"))
            logger.info(f"Order status updated {order_update.order_id} -> {order_update.status}")
            return result
        except HTTPException:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(f"Error updating order status {order_update.order_id}: {exc}")
            raise HTTPException(status_code=500, detail="Internal server error") from exc


async def update_item_status_core(item_update: OrderItemStatusUpdate):
    """Shared logic to update status for an individual order item."""
    async with get_db() as db_conn:
        try:
            service = OrderService()
            result = await service.update_item_status(
                item_update.order_id,
                item_update.sku,
                item_update.status,
                db_conn,
            )
            if not result.get("success", False):
                raise HTTPException(status_code=404, detail=result.get("message", "Order or item not found"))
            logger.info(f"Order item status updated {item_update.order_id}/{item_update.sku} -> {item_update.status}")
            return result
        except HTTPException:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(f"Error updating item status {item_update.order_id}/{item_update.sku}: {exc}")
            raise HTTPException(status_code=500, detail="Internal server error") from exc
